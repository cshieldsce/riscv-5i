#!/usr/bin/env python3
# build_compliance.py: Build the riscv-arch-test RV32I tests for the cocotb
# compliance run. For each test it compiles the .S file, reads the ELF
# segments, runs the program on the reference ISS and writes one JSON file with
# the program image, the signature range and the expected signature.
# Needs a riscv64-unknown-elf toolchain and a riscv-arch-test 3.9.1 checkout.

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys

import rv32i_ref

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_DIR = os.path.join(HERE, "compliance_env")
GCC = "riscv64-unknown-elf-gcc"
NM = "riscv64-unknown-elf-nm"
GCC_FLAGS = ["-march=rv32i", "-mabi=ilp32", "-static", "-mcmodel=medany", "-fvisibility=hidden",
             "-nostdlib", "-nostartfiles", "-DXLEN=32"]


def toolchain_missing():
    return [tool for tool in (GCC, NM) if shutil.which(tool) is None]


def elf_segments(path):
    # (vaddr, bytes) for every PT_LOAD segment of a 32-bit little-endian ELF
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        raise ValueError(f"{path}: not a 32-bit little-endian ELF")
    e_phoff, = struct.unpack_from("<I", data, 0x1C)
    e_phentsize, e_phnum = struct.unpack_from("<HH", data, 0x2A)
    segments = []
    for i in range(e_phnum):
        p_type, p_offset, p_vaddr, _, p_filesz, _, _, _ = struct.unpack_from("<8I", data, e_phoff + i * e_phentsize)
        if p_type == 1 and p_filesz:
            segments.append((p_vaddr, data[p_offset:p_offset + p_filesz]))
    return segments


def split_image(segments, ram_bytes=rv32i_ref.RAM_BYTES):
    # The code segment (starts at 0) becomes the program list, anything else
    # inside RAM becomes data words. Segments outside RAM (tohost) are dropped.
    program, data = [], {}
    for vaddr, blob in segments:
        blob = blob.ljust((len(blob) + 3) // 4 * 4, b"\0")
        words = [int.from_bytes(blob[i:i + 4], "little") for i in range(0, len(blob), 4)]
        if vaddr == 0:
            program = words
        elif vaddr + len(blob) <= ram_bytes:
            data.update({vaddr + 4 * i: w for i, w in enumerate(words)})
    return program, data


def symbol_addresses(elf, names):
    out = subprocess.check_output([NM, elf], text=True)
    found = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in names:
            found[parts[2]] = int(parts[0], 16)
    missing = [n for n in names if n not in found]
    if missing:
        raise ValueError(f"{elf}: missing symbols {missing}")
    return found


def build_one(source, suite_env, out_dir, max_steps=2_000_000):
    name = os.path.basename(source)[:-2]
    elf = os.path.join(out_dir, name + ".elf")
    subprocess.run([GCC, *GCC_FLAGS, "-T", os.path.join(ENV_DIR, "link.ld"), source,
                    "-I" + suite_env, "-I" + ENV_DIR, "-DTEST_CASE_1=True", "-o", elf],
                   check=True, capture_output=True, text=True)
    program, data = split_image(elf_segments(elf))
    sym = symbol_addresses(elf, ["begin_signature", "end_signature"])

    model = rv32i_ref.Rv32iModel(program, data=data)
    model.run(max_steps=max_steps)
    record = {
        "name": name,
        "program": program,
        "data": {str(a): w for a, w in data.items()},
        "sig_begin": sym["begin_signature"],
        "sig_end": sym["end_signature"],
        "model_halted": model.halted,
        "model_steps": model.steps,
        "expected": model.signature(sym["begin_signature"], sym["end_signature"]),
    }
    with open(os.path.join(out_dir, name + ".json"), "w") as f:
        json.dump(record, f)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, help="riscv-arch-test checkout (3.9.1)")
    parser.add_argument("--out", default=os.path.join(HERE, "compliance_build"))
    parser.add_argument("--extension", default="I", help="directory under riscv-test-suite/rv32i_m")
    args = parser.parse_args()

    missing = toolchain_missing()
    if missing:
        sys.exit(f"missing tools: {', '.join(missing)}")
    suite = os.path.join(args.suite, "riscv-test-suite")
    src_dir = os.path.join(suite, "rv32i_m", args.extension, "src")
    if not os.path.isdir(src_dir):
        sys.exit(f"{src_dir} not found, is --suite a riscv-arch-test 3.9.1 checkout?")

    os.makedirs(args.out, exist_ok=True)
    for old in os.listdir(args.out):
        os.remove(os.path.join(args.out, old))
    failures = 0
    for source in sorted(os.listdir(src_dir)):
        if not source.endswith(".S"):
            continue
        try:
            record = build_one(os.path.join(src_dir, source), os.path.join(suite, "env"), args.out)
            status = "ok" if record["model_halted"] else "MODEL DID NOT HALT"
        except (subprocess.CalledProcessError, ValueError) as err:
            status, failures = f"BUILD FAILED: {err}", failures + 1
        print(f"{source:28s} {status}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
