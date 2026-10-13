# rv32i_ref.py: RV32I instruction encoder and a small instruction-set simulator.
# The ISS is the reference model for the compliance run and the random-program
# test. It has the same memory view as the RTL testbench: a read-only
# instruction image, a separate data RAM at the same addresses, a write-only
# LED register at 0x8000_0000 and a tohost register at 0x8000_1000 that ends the run.

MASK = 0xFFFF_FFFF
RAM_BYTES = 4 * 1024 * 1024   # RAM_MEMORY_SIZE words in riscv_pkg.sv
LED_ADDR = 0x8000_0000
TOHOST_ADDR = 0x8000_1000
NOP = 0x0000_0013


def _sx(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


# ---------------- Encoder ---------------- #

def _r(funct7, funct3, opcode, rd, rs1, rs2):
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def _i(funct3, opcode, rd, rs1, imm):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def _s(funct3, rs1, rs2, imm):
    return (((imm >> 5) & 0x7F) << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | ((imm & 0x1F) << 7) | 0x23


def _b(funct3, rs1, rs2, imm):
    return (((imm >> 12) & 1) << 31) | (((imm >> 5) & 0x3F) << 25) | (rs2 << 20) | (rs1 << 15) | \
           (funct3 << 12) | (((imm >> 1) & 0xF) << 8) | (((imm >> 11) & 1) << 7) | 0x63


R_OPS = {"add": (0, 0), "sub": (0x20, 0), "sll": (0, 1), "slt": (0, 2), "sltu": (0, 3),
         "xor": (0, 4), "srl": (0, 5), "sra": (0x20, 5), "or": (0, 6), "and": (0, 7)}
I_OPS = {"addi": 0, "slti": 2, "sltiu": 3, "xori": 4, "ori": 6, "andi": 7}
LOAD_OPS = {"lb": 0, "lh": 1, "lw": 2, "lbu": 4, "lhu": 5}
STORE_OPS = {"sb": 0, "sh": 1, "sw": 2}
BRANCH_OPS = {"beq": 0, "bne": 1, "blt": 4, "bge": 5, "bltu": 6, "bgeu": 7}


def _make_r(name):
    funct7, funct3 = R_OPS[name]
    return lambda rd, rs1, rs2: _r(funct7, funct3, 0x33, rd, rs1, rs2)


def _make_i(name):
    return lambda rd, rs1, imm: _i(I_OPS[name], 0x13, rd, rs1, imm)


def _make_load(name):
    return lambda rd, rs1, imm: _i(LOAD_OPS[name], 0x03, rd, rs1, imm)


def _make_store(name):
    return lambda rs2, rs1, imm: _s(STORE_OPS[name], rs1, rs2, imm)


def _make_branch(name):
    return lambda rs1, rs2, off: _b(BRANCH_OPS[name], rs1, rs2, off)


for _name in R_OPS:
    globals()[_name + ("_" if _name in ("and", "or") else "")] = _make_r(_name)
for _name in I_OPS:
    globals()[_name] = _make_i(_name)
for _name in LOAD_OPS:
    globals()[_name] = _make_load(_name)
for _name in STORE_OPS:
    globals()[_name] = _make_store(_name)
for _name in BRANCH_OPS:
    globals()[_name] = _make_branch(_name)


def slli(rd, rs1, shamt):
    return _r(0, 1, 0x13, rd, rs1, shamt)


def srli(rd, rs1, shamt):
    return _r(0, 5, 0x13, rd, rs1, shamt)


def srai(rd, rs1, shamt):
    return _r(0x20, 5, 0x13, rd, rs1, shamt)


def lui(rd, imm20):
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | 0x37


def auipc(rd, imm20):
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | 0x17


def jal(rd, off):
    return (((off >> 20) & 1) << 31) | (((off >> 1) & 0x3FF) << 21) | (((off >> 11) & 1) << 20) | \
           (((off >> 12) & 0xFF) << 12) | (rd << 7) | 0x6F


def jalr(rd, rs1, imm):
    return _i(0, 0x67, rd, rs1, imm)


def nop():
    return NOP


# ---------------- Simulator ---------------- #

class Rv32iModel:
    def __init__(self, program, data=None):
        # program: list of 32-bit words placed at address 0. The data RAM starts
        # as a copy of the same image (the testbench loads both from one file),
        # then data={addr: word} is laid on top.
        self.imem = {4 * i: w & MASK for i, w in enumerate(program)}
        self.ram = bytearray(RAM_BYTES)
        for addr, word in self.imem.items():
            self.ram[addr:addr + 4] = word.to_bytes(4, "little")
        for addr, word in (data or {}).items():
            self.ram[addr:addr + 4] = (word & MASK).to_bytes(4, "little")
        self.regs = [0] * 32
        self.pc = 0
        self.halted = False
        self.tohost = None
        self.steps = 0

    def imem_word(self, addr):
        return self.imem.get(addr & ~3, NOP)

    def dmem_word(self, addr):
        a = addr & (RAM_BYTES - 1) & ~3
        return int.from_bytes(self.ram[a:a + 4], "little")

    def signature(self, begin, end):
        return [f"{self.dmem_word(a):08x}" for a in range(begin, end, 4)]

    def _write(self, rd, value):
        if rd:
            self.regs[rd] = value & MASK

    def _load(self, addr, funct3):
        a = addr & (RAM_BYTES - 1)
        if funct3 in (0, 4):
            v = self.ram[a]
            return _sx(v, 8) if funct3 == 0 else v
        if funct3 in (1, 5):
            a &= ~1       # the RTL ignores address bit 0 for halfwords
            v = int.from_bytes(self.ram[a:a + 2], "little")
            return _sx(v, 16) if funct3 == 1 else v
        return self.dmem_word(addr)

    def _store(self, addr, value, funct3):
        if addr == LED_ADDR:
            return
        if addr == TOHOST_ADDR:
            self.tohost = value & MASK
            if value & 1:
                self.halted = True
            return
        a = addr & (RAM_BYTES - 1)
        size = {0: 1, 1: 2, 2: 4}[funct3]
        if size == 4:
            a &= ~3
        elif size == 2:
            a &= ~1
        self.ram[a:a + size] = (value & ((1 << (8 * size)) - 1)).to_bytes(size, "little")

    def step(self):
        inst = self.imem_word(self.pc)
        opcode = inst & 0x7F
        rd = (inst >> 7) & 0x1F
        funct3 = (inst >> 12) & 7
        rs1 = (inst >> 15) & 0x1F
        rs2 = (inst >> 20) & 0x1F
        funct7 = inst >> 25
        a, b = self.regs[rs1], self.regs[rs2]
        next_pc = (self.pc + 4) & MASK

        if opcode == 0x33:
            self._write(rd, self._alu(funct3, funct7 == 0x20, a, b))
        elif opcode == 0x13:
            imm = _sx(inst >> 20, 12)
            sub = funct3 == 5 and funct7 == 0x20      # srai
            self._write(rd, self._alu(funct3, sub, a, imm & MASK, immediate=True))
        elif opcode == 0x03:
            self._write(rd, self._load((a + _sx(inst >> 20, 12)) & MASK, funct3))
        elif opcode == 0x23:
            imm = _sx(((inst >> 25) << 5) | ((inst >> 7) & 0x1F), 12)
            self._store((a + imm) & MASK, b, funct3)
        elif opcode == 0x63:
            imm = _sx(((inst >> 31) << 12) | (((inst >> 7) & 1) << 11) |
                      (((inst >> 25) & 0x3F) << 5) | (((inst >> 8) & 0xF) << 1), 13)
            if self._branch_taken(funct3, a, b):
                next_pc = (self.pc + imm) & MASK
        elif opcode == 0x6F:
            imm = _sx(((inst >> 31) << 20) | (((inst >> 12) & 0xFF) << 12) |
                      (((inst >> 20) & 1) << 11) | (((inst >> 21) & 0x3FF) << 1), 21)
            self._write(rd, next_pc)
            next_pc = (self.pc + imm) & MASK
        elif opcode == 0x67:
            target = (a + _sx(inst >> 20, 12)) & MASK & ~1
            self._write(rd, next_pc)
            next_pc = target
        elif opcode == 0x37:
            self._write(rd, inst & 0xFFFFF000)
        elif opcode == 0x17:
            self._write(rd, self.pc + (inst & 0xFFFFF000))
        # SYSTEM and FENCE are NOPs in this core

        self.pc = next_pc
        self.steps += 1

    @staticmethod
    def _alu(funct3, alt, a, b, immediate=False):
        if funct3 == 0:
            return a - b if alt and not immediate else a + b
        if funct3 == 1:
            return a << (b & 31)
        if funct3 == 2:
            return int(_sx(a, 32) < _sx(b, 32))
        if funct3 == 3:
            return int(a < b)
        if funct3 == 4:
            return a ^ b
        if funct3 == 5:
            return (_sx(a, 32) >> (b & 31)) if alt else (a >> (b & 31))
        return a | b if funct3 == 6 else a & b

    @staticmethod
    def _branch_taken(funct3, a, b):
        return {0: a == b, 1: a != b, 4: _sx(a, 32) < _sx(b, 32), 5: _sx(a, 32) >= _sx(b, 32),
                6: a < b, 7: a >= b}[funct3]

    def run(self, max_steps=1_000_000):
        while not self.halted and self.steps < max_steps:
            self.step()
        return self
