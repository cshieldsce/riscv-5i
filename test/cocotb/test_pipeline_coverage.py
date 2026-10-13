# test_pipeline_coverage.py: cocotb testbench for the whole pipeline (CpuTbTop).
# Programs run on the real CPU and memories and the final registers and data
# RAM are compared to the reference ISS (rv32i_ref.py). While they run, a
# sampler watches the forwarding and hazard signals every cycle, checks them
# against a Python model and fills functional coverage bins. The last test
# fails if a reachable bin was never hit.

import random

import cocotb
from cocotb.triggers import Timer

import rv32i_ref as r
from cpu_harness import DATA_BASE, Harness
from funcov import Cross

MAX_CYCLES = 3000
DATA_PRESET = {DATA_BASE: 0xCAFEF00D, DATA_BASE + 4: 0x80000001}
FORWARD_SOURCE = {0b00: "reg", 0b10: "ex_mem", 0b01: "mem_wb"}
PRODUCER_CLASS = {0b00: "alu", 0b01: "load", 0b10: "link"}
OPERANDS = ["A", "B"]


def forward_model(rs, ex_rd, ex_we, wb_rd, wb_we):
    # Same priority as forwarding_unit.sv: EX/MEM wins over MEM/WB, x0 and
    # instructions that don't write never forward
    if ex_we and ex_rd != 0 and ex_rd == rs:
        return 0b10
    if wb_we and wb_rd != 0 and wb_rd == rs:
        return 0b01
    return 0b00


class Coverage:
    def __init__(self):
        self.forward_source = Cross("forwarding source", ("operand", OPERANDS), ("source", list(FORWARD_SOURCE.values())))
        self.forward_producer = Cross("forwarding producer", ("source", ["ex_mem", "mem_wb"]),
                                      ("producer", list(PRODUCER_CLASS.values())))
        self.double_hazard = Cross("double hazard", ("operand", OPERANDS))
        self.no_forward = Cross("no forward despite rd match", ("case", ["x0_ex_mem", "x0_mem_wb", "no_write_ex_mem", "no_write_mem_wb"]),
                                ("operand", OPERANDS))
        self.stall = Cross("stall kind x consumer operand", ("kind", ["load_use", "alu_branch"]),
                           ("operand", ["rs1", "rs2", "both"]))
        self.control = Cross("control hazard", ("event", ["branch_taken", "jalr", "jal"]))
        self.store_data = Cross("store data source", ("source", ["reg", "ex_mem", "mem_wb", "mem_stage_wb"]))
        self.write_through = Cross("register file write-through", ("operand", ["rs1", "rs2"]))

    # (cross, bins that can't happen and why)
    IMPOSSIBLE = {
        # The load-use stall keeps a dependent instruction out of EX while its load is in MEM,
        # and the instructions behind a JAL/JALR are flushed so the first consumer of the
        # link register is already two stages behind it
        "forward_producer": [("ex_mem", "load"), ("ex_mem", "link")],
    }

    def crosses(self):
        return [self.forward_source, self.forward_producer, self.double_hazard, self.no_forward,
                self.stall, self.control, self.store_data, self.write_through]


class Sampler:
    def __init__(self, coverage):
        self.cov = coverage

    def __call__(self, dut):
        c = dut.cpu
        try:
            sig = {name: int(getattr(c, name).value) for name in (
                "forward_a", "forward_b", "id_ex_rs1", "id_ex_rs2", "ex_mem_rd", "ex_mem_reg_write",
                "mem_wb_rd", "mem_wb_reg_write", "ex_mem_wb_mux_sel", "mem_wb_wb_mux_sel",
                "stall_if", "flush_id", "flush_ex", "id_rs1", "id_rs2", "id_branch", "id_jump",
                "id_ex_rd", "id_ex_wb_mux_sel", "branch_taken", "id_ex_jalr", "id_ex_mem_write",
                "ex_mem_mem_write", "ex_mem_rs2")}
        except ValueError:
            return   # still X right after reset

        # Forwarding selects against the model, then bins
        for operand, rs, fwd in (("A", sig["id_ex_rs1"], sig["forward_a"]), ("B", sig["id_ex_rs2"], sig["forward_b"])):
            expected = forward_model(rs, sig["ex_mem_rd"], sig["ex_mem_reg_write"], sig["mem_wb_rd"], sig["mem_wb_reg_write"])
            assert fwd == expected, f"forward_{operand.lower()}={fwd:02b} but the model says {expected:02b} (rs=x{rs}, " \
                f"ex_mem_rd=x{sig['ex_mem_rd']}/{sig['ex_mem_reg_write']}, mem_wb_rd=x{sig['mem_wb_rd']}/{sig['mem_wb_reg_write']})"
            source = FORWARD_SOURCE[fwd]
            self.cov.forward_source.sample(operand, source)
            if source == "ex_mem":
                producer = PRODUCER_CLASS[sig["ex_mem_wb_mux_sel"]]
                assert producer == "alu", f"forwarded {producer} data from EX/MEM, which should never be needed"
                self.cov.forward_producer.sample("ex_mem", producer)
            elif source == "mem_wb":
                self.cov.forward_producer.sample("mem_wb", PRODUCER_CLASS[sig["mem_wb_wb_mux_sel"]])

            ex_match = sig["ex_mem_rd"] == rs
            wb_match = sig["mem_wb_rd"] == rs
            if rs != 0 and ex_match and wb_match and sig["ex_mem_reg_write"] and sig["mem_wb_reg_write"]:
                assert fwd == 0b10
                self.cov.double_hazard.sample(operand)
            if rs == 0 and sig["ex_mem_reg_write"] and sig["ex_mem_rd"] == 0:
                self.cov.no_forward.sample("x0_ex_mem", operand)
            if rs == 0 and sig["mem_wb_reg_write"] and sig["mem_wb_rd"] == 0:
                self.cov.no_forward.sample("x0_mem_wb", operand)
            if rs != 0 and ex_match and not sig["ex_mem_reg_write"]:
                self.cov.no_forward.sample("no_write_ex_mem", operand)
            if rs != 0 and wb_match and not sig["mem_wb_reg_write"]:
                self.cov.no_forward.sample("no_write_mem_wb", operand)

        # Stalls and flushes
        if sig["stall_if"]:
            kind = "load_use" if sig["id_ex_wb_mux_sel"] & 1 else "alu_branch"
            m1 = sig["id_rs1"] == sig["id_ex_rd"]
            m2 = sig["id_rs2"] == sig["id_ex_rd"]
            self.cov.stall.sample(kind, "both" if m1 and m2 else "rs1" if m1 else "rs2")
        if sig["branch_taken"] and not sig["id_ex_jalr"]:
            assert sig["flush_id"] and sig["flush_ex"], "taken branch must flush IF/ID and ID/EX"
            self.cov.control.sample("branch_taken")
        if sig["id_ex_jalr"]:
            assert sig["flush_id"] and sig["flush_ex"], "JALR must flush IF/ID and ID/EX"
            self.cov.control.sample("jalr")
        if sig["id_jump"] and not sig["branch_taken"] and not sig["id_ex_jalr"] and not sig["stall_if"]:
            assert sig["flush_id"] and not sig["flush_ex"], "JAL must flush only IF/ID"
            self.cov.control.sample("jal")

        # Store data: forwarded in EX, or from WB while the store is in MEM
        if sig["id_ex_mem_write"] and not sig["flush_ex"]:
            self.cov.store_data.sample(FORWARD_SOURCE[sig["forward_b"]])
        if sig["ex_mem_mem_write"] and sig["mem_wb_reg_write"] and sig["mem_wb_rd"] != 0 and sig["mem_wb_rd"] == sig["ex_mem_rs2"]:
            self.cov.store_data.sample("mem_stage_wb")

        # Register file write-through: WB writes the register ID is reading
        if sig["mem_wb_reg_write"] and sig["mem_wb_rd"] != 0:
            if sig["id_rs1"] == sig["mem_wb_rd"]:
                self.cov.write_through.sample("rs1")
            if sig["id_rs2"] == sig["mem_wb_rd"]:
                self.cov.write_through.sample("rs2")


coverage = Coverage()
sampler = Sampler(coverage)

BASE_REG = 28     # holds DATA_BASE in the generated programs
PROLOGUE = [r.lui(BASE_REG, DATA_BASE >> 12), r.nop(), r.nop(), r.nop()]
EPILOGUE = [r.lui(31, 0x80001), r.addi(30, 0, 1), r.sw(30, 31, 0)]


async def run_program(dut, name, body):
    # Runs PROLOGUE + body + EPILOGUE on the CPU and on the ISS and compares
    program = PROLOGUE + body + EPILOGUE
    model = r.Rv32iModel(program, data=DATA_PRESET)
    model.run(max_steps=10_000)
    assert model.halted, f"{name}: the ISS never reached the tohost store"

    harness = Harness(dut)
    harness.load(program, DATA_PRESET)
    await harness.reset()
    cycles = await harness.run(MAX_CYCLES, sampler)
    assert cycles is not None, f"{name}: no tohost write in {MAX_CYCLES} cycles"
    await Timer(20, unit="ns")

    for i in range(30):   # x30 and x31 hold the tohost scratch values
        assert harness.reg(i) == model.regs[i], \
            f"{name}: x{i} is {harness.reg(i):08x} but the ISS says {model.regs[i]:08x}"
    for offset in range(0, 64, 4):
        got, want = harness.ram_word(DATA_BASE + offset), model.dmem_word(DATA_BASE + offset)
        assert got == want, f"{name}: RAM[{DATA_BASE + offset:#x}] is {got:08x} but the ISS says {want:08x}"
    return cycles


async def setup(dut):
    harness = Harness(dut)
    await harness.start()
    return harness


# ---------------- Directed programs ---------------- #

PRODUCERS = {
    "alu":   [r.addi(1, 0, 5)],
    "lui":   [r.lui(1, 0x12345)],
    "auipc": [r.auipc(1, 3)],
    "load":  [r.lw(1, BASE_REG, 0)],
    "link":  [r.jal(1, 4)],
}
CONSUMERS = {
    "rs1":       [r.addi(2, 1, 1)],
    "rs2":       [r.add(2, 0, 1)],
    "both":      [r.add(2, 1, 1)],
    "store":     [r.sw(1, BASE_REG, 8)],
    "branch_rs1": [r.bne(1, 0, 8), r.addi(3, 0, 99), r.addi(4, 0, 1)],
    "branch_rs2": [r.bne(0, 1, 8), r.addi(3, 0, 99), r.addi(4, 0, 1)],
    "branch_both": [r.beq(1, 1, 8), r.addi(3, 0, 99), r.addi(4, 0, 1)],
}


@cocotb.test()
async def test_producer_consumer_sweep(dut):
    # Every producer class, 0 to 3 independent instructions in between, and
    # every way a consumer can use the result. Gap 0 forwards from EX/MEM,
    # gap 1 from MEM/WB, gap 2 is the register file write-through.
    dut._log.info("Starting producer/consumer sweep..")
    await setup(dut)
    count = 0
    for producer, p_insts in PRODUCERS.items():
        for gap in range(4):
            filler = [r.addi(20 + i, 0, i + 1) for i in range(gap)]
            for consumer, c_insts in CONSUMERS.items():
                await run_program(dut, f"{producer}+{gap}+{consumer}", p_insts + filler + c_insts)
                count += 1
    dut._log.info(f"PASS: {count} producer/consumer programs match the ISS.")


@cocotb.test()
async def test_special_forwarding_cases(dut):
    dut._log.info("Starting special forwarding cases..")
    await setup(dut)
    cases = {
        # Both EX/MEM and MEM/WB hold x1, the newer value (EX/MEM) must win
        "double_hazard": [r.addi(1, 0, 1), r.addi(1, 1, 2), r.add(2, 1, 1), r.sub(3, 1, 2)],
        # Writes to x0 are dropped and never forwarded
        "x0_dest": [r.addi(0, 0, 7), r.add(1, 0, 0), r.addi(0, 1, 9), r.add(2, 0, 0)],
        # SW and BNE don't write rd but their rd field holds immediate bits.
        # SW offset 8 has rd field x8, BNE offset 16 has rd field x8 too.
        "no_regwrite_store": [r.addi(8, 0, 11), r.sw(0, BASE_REG, 8), r.add(9, 8, 8), r.add(10, 8, 8)],
        "no_regwrite_branch": [r.addi(8, 0, 11), r.bne(0, 0, 16), r.add(9, 8, 8), r.add(10, 8, 8)],
        # Chain through three stages
        "chain": [r.addi(1, 0, 3), r.add(2, 1, 1), r.add(3, 2, 2), r.add(4, 3, 3), r.add(5, 4, 4)],
        # Load result used by a store after a load-use stall, and by a load address
        "load_to_store": [r.lw(1, BASE_REG, 0), r.sw(1, BASE_REG, 12), r.lw(2, BASE_REG, 12), r.sw(2, BASE_REG, 16)],
        # Back-to-back stores of the same just-computed value
        "store_chain": [r.addi(1, 0, 77), r.sw(1, BASE_REG, 20), r.sw(1, BASE_REG, 24), r.sw(1, BASE_REG, 28)],
        # Load-use on rs1, rs2 and both, with the load into x1
        "load_use_rs1": [r.lw(1, BASE_REG, 0), r.addi(2, 1, 1)],
        "load_use_rs2": [r.lw(1, BASE_REG, 0), r.add(2, 0, 1)],
        "load_use_both": [r.lw(1, BASE_REG, 0), r.add(2, 1, 1)],
        # JALR: target from a just-computed register
        "jalr_forwarded": [r.auipc(5, 0), r.jalr(6, 5, 12), r.addi(7, 0, 99), r.addi(8, 0, 5)],
        # Store the AUIPC result, load it back and JALR to it + 28, which is the last ADDI
        "jalr_after_load": [r.auipc(9, 0), r.sw(9, BASE_REG, 4), r.nop(), r.nop(),
                            r.lw(5, BASE_REG, 4), r.jalr(6, 5, 28), r.addi(7, 0, 1), r.addi(10, 0, 2)],
    }
    for name, body in cases.items():
        await run_program(dut, name, body)
    dut._log.info(f"PASS: {len(cases)} special cases match the ISS.")


@cocotb.test()
async def test_control_hazards(dut):
    dut._log.info("Starting control hazard programs..")
    await setup(dut)
    cases = {
        "taken_branch_flush": [r.beq(0, 0, 12), r.addi(1, 0, 1), r.addi(2, 0, 2), r.addi(3, 0, 3)],
        "not_taken_branch": [r.bne(0, 0, 12), r.addi(1, 0, 1), r.addi(2, 0, 2), r.addi(3, 0, 3)],
        "jal_flush": [r.jal(1, 12), r.addi(2, 0, 2), r.addi(3, 0, 3), r.addi(4, 0, 4)],
        "jal_chain": [r.jal(1, 8), r.addi(2, 0, 2), r.jal(3, 8), r.addi(4, 0, 4), r.addi(5, 0, 5)],
        "branch_over_branch": [r.beq(0, 0, 8), r.addi(1, 0, 1), r.beq(0, 0, 8), r.addi(2, 0, 2), r.addi(3, 0, 3)],
        "branch_then_jal": [r.beq(0, 0, 8), r.addi(1, 0, 1), r.jal(2, 8), r.addi(3, 0, 3), r.addi(4, 0, 4)],
        "alu_branch_stall": [r.addi(1, 0, 4), r.beq(1, 1, 8), r.addi(2, 0, 2), r.addi(3, 0, 3)],
        "load_branch_stall": [r.lw(1, BASE_REG, 0), r.beq(1, 1, 8), r.addi(2, 0, 2), r.addi(3, 0, 3)],
        "backward_branch_loop": [r.addi(1, 0, 3), r.addi(1, 1, -1), r.bne(1, 0, -4), r.addi(2, 0, 9)],
    }
    for name, body in cases.items():
        await run_program(dut, name, body)
    dut._log.info(f"PASS: {len(cases)} control-flow programs match the ISS.")


# ---------------- Random programs ---------------- #

REG_POOL = list(range(1, 8))    # a small pool so dependencies are everywhere
R_OPS = [r.add, r.sub, r.sll, r.slt, r.sltu, r.xor, r.srl, r.sra, r.or_, r.and_]
I_OPS = [r.addi, r.slti, r.sltiu, r.xori, r.ori, r.andi]
SHIFT_OPS = [r.slli, r.srli, r.srai]
LOADS = [r.lb, r.lbu, r.lw]


def random_body(rng, length):
    # Short random basic blocks. Branches and JAL only go forward over the
    # next instruction, JALR is an AUIPC/JALR pair that skips one instruction.
    # SB and SH only use byte offset 0: SB/SH to other offsets fail on the
    # current RTL (see compliance_known_failures.txt) and would drown out
    # everything else this test is looking for.
    pick = lambda: rng.choice(REG_POOL)
    body = []
    while len(body) < length:
        kind = rng.random()
        if kind < 0.30:
            body.append(rng.choice(R_OPS)(pick(), pick(), pick()))
        elif kind < 0.50:
            body.append(rng.choice(I_OPS)(pick(), pick(), rng.randint(-2048, 2047)))
        elif kind < 0.55:
            body.append(rng.choice(SHIFT_OPS)(pick(), pick(), rng.randint(0, 31)))
        elif kind < 0.60:
            body.append(rng.choice([r.lui, r.auipc])(pick(), rng.getrandbits(20)))
        elif kind < 0.72:
            op = rng.choice(LOADS + [r.lh, r.lhu])
            align = 4 if op is r.lw else 2 if op in (r.lh, r.lhu) else 1
            body.append(op(pick(), BASE_REG, rng.randrange(0, 60, align)))
        elif kind < 0.82:
            op = rng.choice([r.sw, r.sw, r.sh, r.sb])
            body.append(op(pick(), BASE_REG, rng.randrange(0, 60, 4)))
        elif kind < 0.92:
            op = rng.choice([r.beq, r.bne, r.blt, r.bge, r.bltu, r.bgeu])
            body += [op(pick(), pick(), 8), rng.choice(I_OPS)(pick(), pick(), rng.randint(-8, 8))]
        elif kind < 0.96:
            body += [r.jal(pick(), 8), r.addi(pick(), pick(), 1)]
        else:
            t = pick()
            link = pick()
            body += [r.auipc(t, 0), r.jalr(link if link != t else 0, t, 12), r.addi(pick(), pick(), 1)]
    return body


@cocotb.test()
async def test_random_programs(dut):
    dut._log.info("Starting random programs..")
    rng = random.Random(0x5EED)
    await setup(dut)
    count = 150
    for n in range(count):
        await run_program(dut, f"random_{n}", random_body(rng, 60))
    dut._log.info(f"PASS: {count} random programs match the ISS.")


# ---------------- Coverage closure (keep this test last) ---------------- #

@cocotb.test()
async def test_zz_coverage_closed(dut):
    # cocotb runs tests in file order, so this sees what the others sampled.
    # Running it alone (TESTCASE=...) fails by design.
    missed = []
    for cross in coverage.crosses():
        cross.report(dut._log)
        attr = next(name for name, value in vars(coverage).items() if value is cross)
        impossible = Coverage.IMPOSSIBLE.get(attr, [])
        missed += [(cross.name, b) for b in cross.missing() if b not in impossible]
    assert not missed, f"FAIL: reachable bins never hit: {missed}"
    dut._log.info("PASS: Every reachable hazard and forwarding bin was hit.")
