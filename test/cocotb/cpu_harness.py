# cpu_harness.py: Helpers shared by the cocotb tests that drive CpuTbTop
# (cpu_tb_top.sv): clock and reset, loading a program, running until the
# program stores to tohost, and reading the data RAM back.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer

NOP = 0x0000_0013
CLEAN_WORDS = 256   # data RAM words at DATA_BASE put back to 0 before each program
TOHOST_ADDR = 0x8000_1000
DATA_BASE = 0x0020_0000
TOHOST_ADDR_ALIAS = (TOHOST_ADDR & 0x3F_FFFF) // 4   # DataMemory only decodes the low 22 address bits


class Harness:
    def __init__(self, dut):
        self.dut = dut
        self.imem_dirty = set()
        self.ram_dirty = set()

    async def start(self):
        # 10 ns clock. Reset is held for two edges, same as pipelined_cpu_tb.sv.
        self.dut.rst.value = 1
        cocotb.start_soon(Clock(self.dut.clk, 10, unit="ns").start())
        await Timer(1, unit="ns")

    def load(self, program, data=None, pad=16):
        # program goes into the instruction memory and, like the existing
        # testbench, into the data RAM too. data={addr: word} goes to RAM only.
        # Words from the previous program are put back to NOP / 0 first, and so
        # is the start of the data region, since the program itself stores there.
        for i in self.imem_dirty:
            self.dut.imem.rom_memory[i].value = NOP
        for i in self.ram_dirty:
            self.dut.dmem.ram_memory[i].value = 0
        for i in range(CLEAN_WORDS):
            self.dut.dmem.ram_memory[DATA_BASE // 4 + i].value = 0
        self.imem_dirty, self.ram_dirty = set(), set()
        self.ram_dirty.add(TOHOST_ADDR_ALIAS)   # the tohost store lands here, see data_memory.sv

        for i, word in enumerate(list(program) + [NOP] * pad):
            self.dut.imem.rom_memory[i].value = word
            self.imem_dirty.add(i)
        for i, word in enumerate(program):
            self.dut.dmem.ram_memory[i].value = word
            self.ram_dirty.add(i)
        for addr, word in (data or {}).items():
            self.dut.dmem.ram_memory[addr // 4].value = word
            self.ram_dirty.add(addr // 4)

    async def reset(self, cycles=2):
        self.dut.rst.value = 1
        for _ in range(cycles):
            await RisingEdge(self.dut.clk)
        self.dut.rst.value = 0

    async def run(self, max_cycles, on_cycle=None):
        # Runs until a store to tohost shows up in MEM. Returns the cycle count,
        # or None if max_cycles went by first. on_cycle(dut) is called once per
        # cycle with the settled signals, for the coverage sampling.
        for cycle in range(max_cycles):
            await RisingEdge(self.dut.clk)
            await ReadOnly()
            if on_cycle is not None:
                on_cycle(self.dut)
            if int(self.dut.dmem_we.value) and int(self.dut.dmem_addr.value) == TOHOST_ADDR:
                return cycle
            await Timer(1, unit="ns")   # leave ReadOnly before the next edge
        return None

    def ram_word(self, addr):
        return int(self.dut.dmem.ram_memory[addr // 4].value)

    def reg(self, index):
        return int(self.dut.cpu.id_stage_inst.reg_file_inst.register_memory[index].value)

    def regs(self):
        return [self.reg(i) for i in range(32)]
