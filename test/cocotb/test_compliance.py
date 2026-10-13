# test_compliance.py: cocotb run of the riscv-arch-test RV32I programs.
# build_compliance.py compiles every test and runs it on the reference ISS;
# this runs the same image on the pipelined CPU and compares the signatures.
# One row per test goes to results_compliance.md. With no built tests it skips.
#
# compliance_known_failures.txt lists tests that fail because of a known RTL
# bug. They show up as XFAIL and don't fail the run, but if one starts passing
# it shows as XPASS and fails the run so the entry gets removed.

import glob
import json
import os

import cocotb
from cocotb.triggers import Timer

from cpu_harness import Harness

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.environ.get("COMPLIANCE_BUILD", os.path.join(HERE, "compliance_build"))
MAX_CYCLES = 400_000
TABLE_FILE = "results_compliance.md"


def read_known_failures(path):
    known = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#"):
            name, _, reason = line.partition(" ")
            known[name] = reason.strip()
    return known


records = {}
for path in sorted(glob.glob(os.path.join(BUILD_DIR, "*.json"))):
    record = json.load(open(path))
    records[record["name"]] = record
known_failures = read_known_failures(os.path.join(HERE, "compliance_known_failures.txt"))
rows = []


def write_table():
    passed = sum(1 for row in rows if row[1] == "PASS")
    xfail = sum(1 for row in rows if row[1] == "XFAIL")
    with open(TABLE_FILE, "w") as f:
        f.write("| Test | Result | Signature words | Cycles | Detail |\n|---|---|---:|---:|---|\n")
        for name, result, words, cycles, detail in rows:
            f.write(f"| {name} | {result} | {words} | {cycles} | {detail} |\n")
        f.write(f"\n**{passed}/{len(rows)} pass, {xfail} known failures**\n")


async def run_record(dut, record):
    harness = Harness(dut)
    await harness.start()
    harness.load(record["program"], {int(a): w for a, w in record["data"].items()})
    await harness.reset()
    cycles = await harness.run(MAX_CYCLES)
    await Timer(50, unit="ns")   # let the last stores land

    expected = record["expected"]
    if cycles is None:
        return "FAIL", len(expected), "-", f"no tohost write in {MAX_CYCLES} cycles"
    actual = [f"{harness.ram_word(a):08x}" for a in range(record["sig_begin"], record["sig_end"], 4)]
    mismatches = [i for i, (a, e) in enumerate(zip(actual, expected)) if a != e]
    if mismatches:
        i = mismatches[0]
        detail = f"{len(mismatches)} words differ, first at word {i}: got {actual[i]}, expected {expected[i]}"
        return "FAIL", len(expected), cycles, detail
    return "PASS", len(expected), cycles, ""


if records:
    @cocotb.parametrize(name=list(records))
    async def test_arch_test(dut, name):
        result, words, cycles, detail = await run_record(dut, records[name])
        if name in known_failures:
            if result == "FAIL":
                result, detail = "XFAIL", f"{known_failures[name]} ({detail})"
            elif result == "PASS":
                result, detail = "XPASS", "listed in compliance_known_failures.txt but passes, remove the entry"
        rows.append((name, result, words, cycles, detail))
        write_table()
        assert result in ("PASS", "XFAIL"), f"{name}: {result} {detail}"
else:
    @cocotb.test(skip=True)
    async def test_arch_test(dut):
        # Run 'make compliance ARCH_TEST=<riscv-arch-test 3.9.1 checkout>' to build the tests first
        pass
