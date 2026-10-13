# test_ref_model.py: pytest checks for rv32i_ref.py (the encoder and the ISS).
# Pure Python, no simulator. Encodings come from the RISC-V spec / objdump, not
# from the encoder, so a mistake in rv32i_ref.py can't hide itself.

import pytest

import rv32i_ref as r

# (encoder call, expected machine word), values taken from riscv64-unknown-elf-objdump
KNOWN_ENCODINGS = [
    (lambda: r.addi(0, 0, 0),        0x00000013),   # nop
    (lambda: r.addi(1, 0, -1),       0xFFF00093),
    (lambda: r.add(3, 1, 2),         0x002081B3),
    (lambda: r.sub(3, 1, 2),         0x402081B3),
    (lambda: r.sra(5, 6, 7),         0x407352B3),
    (lambda: r.srai(5, 6, 31),       0x41F35293),
    (lambda: r.lui(2, 0x12345),      0x12345137),
    (lambda: r.auipc(1, 1),          0x00001097),
    (lambda: r.lw(4, 2, 8),          0x00812203),
    (lambda: r.sw(4, 2, -4),         0xFE412E23),
    (lambda: r.beq(1, 2, 8),         0x00208463),
    (lambda: r.bne(1, 2, -4),        0xFE209EE3),
    (lambda: r.jal(1, 2048),         0x001000EF),
    (lambda: r.jalr(0, 1, 0),        0x00008067),
]


@pytest.mark.parametrize("make,word", KNOWN_ENCODINGS)
def test_encodings(make, word):
    assert make() == word, f"expected {word:08x} but got {make():08x}"


def run(program, **kwargs):
    cpu = r.Rv32iModel(program)
    cpu.run(**kwargs)
    return cpu


def test_x0_is_hardwired_to_zero():
    cpu = run([r.addi(0, 0, 5), r.add(1, 0, 0)], max_steps=2)
    assert cpu.regs[0] == 0 and cpu.regs[1] == 0


def test_arithmetic_wraps_to_32_bits():
    cpu = run([r.lui(1, 0x80000), r.addi(2, 0, -1), r.add(3, 1, 1), r.sub(4, 1, 2)], max_steps=4)
    assert cpu.regs[3] == 0
    assert cpu.regs[4] == 0x80000001


def test_slt_signed_vs_unsigned():
    cpu = run([r.addi(1, 0, -1), r.addi(2, 0, 1),
               r.slt(3, 1, 2), r.sltu(4, 1, 2), r.slti(5, 1, 0), r.sltiu(6, 2, -1)], max_steps=6)
    assert (cpu.regs[3], cpu.regs[4], cpu.regs[5], cpu.regs[6]) == (1, 0, 1, 1)


def test_shifts_use_low_five_bits_and_sra_keeps_sign():
    cpu = run([r.lui(1, 0x80000), r.addi(2, 0, 36),
               r.srl(3, 1, 2), r.sra(4, 1, 2), r.sll(5, 1, 2), r.srai(6, 1, 31)], max_steps=6)
    assert cpu.regs[3] == 0x08000000
    assert cpu.regs[4] == 0xF8000000
    assert cpu.regs[5] == 0
    assert cpu.regs[6] == 0xFFFFFFFF


def test_branch_taken_and_not_taken():
    prog = [r.addi(1, 0, 1), r.beq(1, 0, 8), r.addi(2, 0, 7),   # not taken, x2 = 7
            r.bne(1, 0, 8), r.addi(3, 0, 9), r.addi(4, 0, 4)]   # taken, x3 stays 0
    cpu = run(prog, max_steps=6)
    assert (cpu.regs[2], cpu.regs[3], cpu.regs[4]) == (7, 0, 4)


def test_signed_vs_unsigned_branches():
    prog = [r.addi(1, 0, -1), r.addi(2, 0, 1),
            r.blt(1, 2, 8), r.addi(3, 0, 1),     # taken: skip
            r.bltu(1, 2, 8), r.addi(4, 0, 1)]    # not taken: x4 = 1
    cpu = run(prog, max_steps=6)
    assert (cpu.regs[3], cpu.regs[4]) == (0, 1)


def test_jal_and_jalr_link_and_clear_lsb():
    prog = [r.jal(1, 8), r.addi(5, 0, 1), r.addi(2, 0, 21), r.jalr(3, 2, 0), r.addi(6, 0, 1), r.addi(7, 0, 3)]
    cpu = run(prog, max_steps=5)
    assert cpu.regs[1] == 4
    assert cpu.regs[5] == 0             # skipped by JAL
    assert cpu.regs[3] == 16            # link is the pc after jalr
    assert cpu.regs[6] == 0             # skipped: 21 & ~1 = 20
    assert cpu.regs[7] == 3


def test_lui_auipc():
    cpu = run([r.lui(1, 0xFFFFF), r.auipc(2, 1)], max_steps=2)
    assert cpu.regs[1] == 0xFFFFF000
    assert cpu.regs[2] == 4 + 0x1000


def test_loads_and_stores_sub_word():
    base = 0x200000
    prog = [r.lui(1, base >> 12), r.addi(2, 0, -2),          # x2 = 0xFFFFFFFE
            r.sw(2, 1, 0), r.sb(0, 1, 1),
            r.lw(3, 1, 0), r.lb(4, 1, 0), r.lbu(5, 1, 0), r.lh(6, 1, 2), r.lhu(7, 1, 2)]
    cpu = run(prog, max_steps=9)
    assert cpu.regs[3] == 0xFFFF00FE
    assert cpu.regs[4] == 0xFFFFFFFE
    assert cpu.regs[5] == 0xFE
    assert cpu.regs[6] == 0xFFFFFFFF
    assert cpu.regs[7] == 0xFFFF


def test_store_to_tohost_stops_the_run():
    prog = [r.lui(1, 0x80001), r.addi(2, 0, 1), r.sw(2, 1, 0), r.addi(3, 0, 5)]
    cpu = run(prog, max_steps=100)
    assert cpu.halted and cpu.regs[3] == 0


def test_stores_do_not_change_instruction_memory():
    # Harvard like the RTL: a store to the code region only reaches the data side
    prog = [r.addi(1, 0, 0x55), r.sw(1, 0, 8), r.addi(2, 0, 1)]
    cpu = run(prog, max_steps=3)
    assert cpu.imem_word(8) == r.addi(2, 0, 1)
    assert cpu.dmem_word(8) == 0x55


def test_signature_slice_reads_data_memory():
    cpu = r.Rv32iModel([r.nop()], data={0x200000: 0xDEADBEEF, 0x200004: 1})
    assert cpu.signature(0x200000, 0x200008) == ["deadbeef", "00000001"]
