# test_build_compliance.py: pytest checks for build_compliance.py. The ELF
# parsing runs on a hand-built ELF so it needs no toolchain. The end-to-end
# check assembles a tiny program and is skipped without riscv64-unknown-elf-gcc.

import os
import struct

import pytest

import build_compliance as bc
import rv32i_ref as r


def make_elf(segments):
    # Minimal 32-bit little-endian ELF with only program headers: [(vaddr, bytes)]
    phoff, phentsize = 52, 32
    header = b"\x7fELF" + bytes([1, 1, 1, 0]) + bytes(8)
    header += struct.pack("<HHIIIIIHHHHHH", 2, 243, 1, 0, phoff, 0, 0, 52, phentsize, len(segments), 40, 0, 0)
    offset = phoff + phentsize * len(segments)
    phdrs, blobs = b"", b""
    for vaddr, blob in segments:
        phdrs += struct.pack("<8I", 1, offset + len(blobs), vaddr, vaddr, len(blob), len(blob), 5, 4)
        blobs += blob
    return header + phdrs + blobs


def test_elf_segments_round_trip(tmp_path):
    code = r.addi(1, 0, 5).to_bytes(4, "little") + r.nop().to_bytes(4, "little")
    path = tmp_path / "t.elf"
    path.write_bytes(make_elf([(0, code), (0x200000, b"\x01\x02\x03\x04")]))
    assert bc.elf_segments(str(path)) == [(0, code), (0x200000, b"\x01\x02\x03\x04")]


def test_elf_rejects_non_elf(tmp_path):
    path = tmp_path / "bad.elf"
    path.write_bytes(b"not an elf at all")
    with pytest.raises(ValueError):
        bc.elf_segments(str(path))


def test_split_image_sorts_code_data_and_drops_mmio():
    segments = [(0, b"\x13\x00\x00\x00"), (0x200000, b"\xef\xbe\xad\xde\x01"), (0x80001000, b"\x01\x00\x00\x00")]
    program, data = bc.split_image(segments)
    assert program == [0x13]
    assert data == {0x200000: 0xDEADBEEF, 0x200004: 0x01}   # trailing partial word is zero padded


@pytest.mark.skipif(bc.toolchain_missing(), reason="needs riscv64-unknown-elf-gcc")
def test_assembled_program_matches_encoder(tmp_path):
    src = tmp_path / "t.S"
    src.write_text(".text\n.globl _start\n_start:\n addi x1, x0, -1\n add x3, x1, x2\n sw x3, 0(x0)\n")
    elf = tmp_path / "t.elf"
    import subprocess
    subprocess.run([bc.GCC, "-march=rv32i", "-mabi=ilp32", "-nostdlib", "-nostartfiles", "-Ttext=0", str(src), "-o", str(elf)], check=True)
    program, _ = bc.split_image(bc.elf_segments(str(elf)))
    assert program == [r.addi(1, 0, -1), r.add(3, 1, 2), r.sw(3, 0, 0)]
