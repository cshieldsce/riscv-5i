# test_alu.py: cocotb testbench for the ALU (src/alu.sv).
# Every result gets checked against a Python model of the ALU. The first test
# walks every op through every pair of operand classes and every shift amount,
# the second throws random ops at it, and the third checks the unused codes.

import random

import cocotb
from cocotb.triggers import Timer

from funcov import Cross

XLEN = 32
MASK = (1 << XLEN) - 1

# ALUControl encodings, copied from alu_op_t in riscv_pkg.sv
ALU_OPS = {
    "ADD":  0b0010,
    "SUB":  0b0110,
    "AND":  0b0000,
    "OR":   0b0001,
    "XOR":  0b1001,
    "SLL":  0b1010,
    "SRL":  0b1011,
    "SRA":  0b1100,
    "SLT":  0b0111,
    "SLTU": 0b1000,
}
UNUSED_CODES = sorted(set(range(16)) - set(ALU_OPS.values()))

# Operand classes: the edge values plus a small and a fully random number
OPERAND_CLASSES = {
    "zero":     lambda: 0,
    "all_ones": lambda: MASK,
    "max_pos":  lambda: 0x7FFF_FFFF,
    "min_neg":  lambda: 0x8000_0000,
    "small":    lambda: random.randint(1, 255),
    "random":   lambda: random.getrandbits(XLEN),
}


def to_signed(value):
    # Reinterpret a 32-bit value as two's complement
    if value & (1 << (XLEN - 1)):
        return value - (1 << XLEN)
    return value


def alu_model(op, a, b):
    # Shifts only use the low 5 bits of B, same as the RTL
    shamt = b & 0x1F

    if op == "ADD":
        return (a + b) & MASK
    if op == "SUB":
        return (a - b) & MASK
    if op == "AND":
        return a & b
    if op == "OR":
        return a | b
    if op == "XOR":
        return a ^ b
    if op == "SLL":
        return (a << shamt) & MASK
    if op == "SRL":
        return a >> shamt
    if op == "SRA":
        return (to_signed(a) >> shamt) & MASK
    if op == "SLT":
        return int(to_signed(a) < to_signed(b))
    if op == "SLTU":
        return int(a < b)
    raise ValueError(f"Unknown op {op}")


async def check_op(dut, op, a, b):
    dut.A.value = a
    dut.B.value = b
    dut.ALUControl.value = ALU_OPS[op]
    await Timer(1, unit="ns")  # Combinational, just let it settle

    expected = alu_model(op, a, b)
    result = int(dut.Result.value)
    zero = int(dut.Zero.value)
    assert result == expected, (
        f"FAIL: {op} Test. A=0x{a:08x} B=0x{b:08x} Expected=0x{expected:08x} but got Result=0x{result:08x}")
    assert zero == int(expected == 0), (
        f"FAIL: {op} Zero flag. Result=0x{expected:08x} Expected Zero={int(expected == 0)} but got Zero={zero}")


@cocotb.test()
async def test_alu_ops_and_operand_classes(dut):
    dut._log.info("Starting ALU op and operand class test..")
    random.seed(1)

    # 1. Every op against every pair of operand classes (10 x 6 x 6 = 360 bins)
    op_coverage = Cross("op x A class x B class",
                        ("op", ALU_OPS), ("a_class", OPERAND_CLASSES), ("b_class", OPERAND_CLASSES))
    for op in ALU_OPS:
        for a_class, make_a in OPERAND_CLASSES.items():
            for b_class, make_b in OPERAND_CLASSES.items():
                await check_op(dut, op, make_a(), make_b())
                op_coverage.sample(op, a_class, b_class)

    # 2. Every shift amount for all three shifts (3 x 32 = 96 bins). The upper
    # bits of B get junk in them because the shifter should ignore bits 31:5.
    shift_coverage = Cross("shift op x shift amount", ("op", ["SLL", "SRL", "SRA"]), ("shamt", range(XLEN)))
    for op in ("SLL", "SRL", "SRA"):
        for shamt in range(XLEN):
            b = shamt | (random.getrandbits(XLEN - 5) << 5)
            for a in (0x8000_0001, random.getrandbits(XLEN)):
                await check_op(dut, op, a, b)
            shift_coverage.sample(op, shamt)

    op_coverage.report(dut._log)
    shift_coverage.report(dut._log)
    assert not op_coverage.missing(), "FAIL: Some op x operand class bins were never hit"
    assert not shift_coverage.missing(), "FAIL: Some shift amounts were never hit"
    dut._log.info("PASS: All ops, operand classes and shift amounts match the model.")


@cocotb.test()
async def test_alu_random(dut):
    # 4000 random ops. Operands come from the same classes so the edge values
    # still show up a lot instead of almost never.
    dut._log.info("Starting ALU random test..")
    random.seed(0xA1)

    op_counts = Cross("random ops", ("op", ALU_OPS))
    for _ in range(4000):
        op = random.choice(list(ALU_OPS))
        a = random.choice(list(OPERAND_CLASSES.values()))()
        b = random.choice(list(OPERAND_CLASSES.values()))()
        await check_op(dut, op, a, b)
        op_counts.sample(op)

    op_counts.report(dut._log)
    assert not op_counts.missing(), "FAIL: The random test never picked some ops"
    dut._log.info("PASS: 4000 random ops match the model.")


@cocotb.test()
async def test_alu_unused_codes_output_zero(dut):
    # The default case in alu.sv should output 0 for the codes nothing uses
    dut._log.info("Starting ALU unused code test..")

    for code in UNUSED_CODES:
        dut.A.value = 0xDEAD_BEEF
        dut.B.value = 0x1234_5678
        dut.ALUControl.value = code
        await Timer(1, unit="ns")

        result = int(dut.Result.value)
        assert result == 0, f"FAIL: Unused code 4'b{code:04b}. Expected=0 but got Result=0x{result:08x}"
        assert int(dut.Zero.value) == 1, f"FAIL: Unused code 4'b{code:04b}. Expected Zero=1"

    dut._log.info(f"PASS: All {len(UNUSED_CODES)} unused codes output 0.")
