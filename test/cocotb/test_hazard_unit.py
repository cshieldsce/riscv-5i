# test_hazard_unit.py: cocotb testbench for the HazardUnit (src/hazard_unit.sv).
# A Python model of the same priority chain gets compared against the RTL for
# every hazard type through every register match, then with random vectors.

import random

import cocotb
from cocotb.triggers import Timer

from funcov import Cross

HAZARD_TYPES = ["load_use", "alu_branch", "branch_taken", "jal", "none"]
REGISTER_MATCHES = ["rs1", "rs2", "both", "x0", "no_match"]

# Load-use and ALU-to-branch need rd to match a source register, so these
# four bins can't happen
IMPOSSIBLE_BINS = [(hazard, match) for hazard in ("load_use", "alu_branch") for match in ("x0", "no_match")]


def has_register_dependency(rd, rs1, rs2):
    # Same as the RTL function: rd matches a source register and isn't x0
    return rd != 0 and (rd == rs1 or rd == rs2)


def hazard_type(rs1, rs2, id_branch, ex_rd, ex_mem_read, branch_taken_ex, jump_id_stage):
    # Which branch of the priority chain these inputs land in
    dependency = has_register_dependency(ex_rd, rs1, rs2)
    if ex_mem_read and dependency:
        return "load_use"
    if not ex_mem_read and id_branch and dependency:
        return "alu_branch"
    if branch_taken_ex:
        return "branch_taken"
    if jump_id_stage:
        return "jal"
    return "none"


def hazard_model(rs1, rs2, id_branch, ex_rd, ex_mem_read, branch_taken_ex, jump_id_stage):
    expected = {"stall_if": 0, "stall_id": 0, "flush_ex": 0, "flush_id": 0}
    hazard = hazard_type(rs1, rs2, id_branch, ex_rd, ex_mem_read, branch_taken_ex, jump_id_stage)

    if hazard in ("load_use", "alu_branch"):
        # 1 and 2. Stall IF and ID, insert a bubble into EX
        expected.update(stall_if=1, stall_id=1, flush_ex=1)
    elif hazard == "branch_taken":
        # 3. Taken branch or JALR: flush IF/ID and ID/EX
        expected.update(flush_id=1, flush_ex=1)
    elif hazard == "jal":
        # 4. JAL resolves in ID so only IF/ID gets flushed
        expected.update(flush_id=1)
    return expected


def register_match(rs1, rs2, ex_rd):
    if ex_rd == 0 and (rs1 == 0 or rs2 == 0):
        return "x0"
    if ex_rd == rs1 and ex_rd == rs2:
        return "both"
    if ex_rd == rs1:
        return "rs1"
    if ex_rd == rs2:
        return "rs2"
    return "no_match"


def pick_registers(match):
    # Returns (rs1, rs2, ex_rd) lined up the way match says
    rd = random.randint(1, 31)
    other = random.choice([r for r in range(32) if r != rd])
    if match == "rs1":
        return rd, other, rd
    if match == "rs2":
        return other, rd, rd
    if match == "both":
        return rd, rd, rd
    if match == "x0":
        return 0, random.randint(0, 31), 0
    return other, random.choice([r for r in range(32) if r != rd]), rd


async def check_hazard(dut, rs1, rs2, id_branch, ex_rd, ex_mem_read, branch_taken_ex, jump_id_stage):
    dut.id_rs1.value = rs1
    dut.id_rs2.value = rs2
    dut.id_branch.value = id_branch
    dut.id_ex_rd.value = ex_rd
    dut.id_ex_mem_read.value = ex_mem_read
    dut.branch_taken_ex.value = branch_taken_ex
    dut.jump_id_stage.value = jump_id_stage
    await Timer(1, unit="ns")  # Combinational, just let it settle

    expected = hazard_model(rs1, rs2, id_branch, ex_rd, ex_mem_read, branch_taken_ex, jump_id_stage)
    actual = {name: int(getattr(dut, name).value) for name in expected}
    assert actual == expected, (
        f"FAIL: rs1=x{rs1} rs2=x{rs2} id_branch={id_branch} ex_rd=x{ex_rd} ex_mem_read={ex_mem_read} "
        f"branch_taken_ex={branch_taken_ex} jump_id_stage={jump_id_stage}. Expected={expected} but got {actual}")


@cocotb.test()
async def test_hazard_priority_chain(dut):
    # Every hazard type through every register match (5 x 5 = 25 bins). The
    # lower priority inputs get set randomly too, so a hazard only passes if
    # it wins over everything below it.
    dut._log.info("Starting HazardUnit priority test..")
    random.seed(7)

    coverage = Cross("hazard type x register match", ("type", HAZARD_TYPES), ("match", REGISTER_MATCHES))
    for wanted in HAZARD_TYPES:
        for match in REGISTER_MATCHES:
            if (wanted, match) in IMPOSSIBLE_BINS:
                continue

            for _ in range(8):
                rs1, rs2, ex_rd = pick_registers(match)
                dependency = has_register_dependency(ex_rd, rs1, rs2)
                id_branch = ex_mem_read = branch_taken_ex = jump_id_stage = 0

                if wanted == "load_use":
                    ex_mem_read = 1
                    id_branch = random.getrandbits(1)
                    branch_taken_ex = random.getrandbits(1)
                    jump_id_stage = random.getrandbits(1)
                elif wanted == "alu_branch":
                    id_branch = 1
                    branch_taken_ex = random.getrandbits(1)
                    jump_id_stage = random.getrandbits(1)
                elif wanted == "branch_taken":
                    branch_taken_ex = 1
                    jump_id_stage = random.getrandbits(1)
                    # With a dependency, id_branch=1 would make this an ALU-to-branch hazard instead
                    if not dependency:
                        id_branch = random.getrandbits(1)
                elif wanted == "jal":
                    jump_id_stage = 1
                    if not dependency:
                        id_branch = random.getrandbits(1)

                await check_hazard(dut, rs1, rs2, id_branch, ex_rd, ex_mem_read, branch_taken_ex, jump_id_stage)
                coverage.sample(hazard_type(rs1, rs2, id_branch, ex_rd, ex_mem_read, branch_taken_ex, jump_id_stage),
                                register_match(rs1, rs2, ex_rd))

    coverage.report(dut._log)
    reachable_misses = [b for b in coverage.missing() if b not in IMPOSSIBLE_BINS]
    assert not reachable_misses, f"FAIL: Reachable bins never hit: {reachable_misses}"
    dut._log.info("PASS: Every reachable hazard type and register match agrees with the model.")


@cocotb.test()
async def test_hazard_random(dut):
    # 5000 random input vectors. Half the time ex_rd gets copied from rs1 or
    # rs2, otherwise almost nothing would have a dependency.
    dut._log.info("Starting HazardUnit random test..")
    random.seed(0x5A)

    type_counts = Cross("random hazard types", ("type", HAZARD_TYPES))
    for _ in range(5000):
        rs1 = random.randint(0, 31)
        rs2 = random.randint(0, 31)
        ex_rd = random.randint(0, 31)
        if random.random() < 0.5:
            ex_rd = random.choice((rs1, rs2))

        inputs = (rs1, rs2, random.getrandbits(1), ex_rd, random.getrandbits(1),
                  random.getrandbits(1), random.getrandbits(1))
        await check_hazard(dut, *inputs)
        type_counts.sample(hazard_type(*inputs))

    type_counts.report(dut._log)
    assert not type_counts.missing(), "FAIL: The random test never produced some hazard types"
    dut._log.info("PASS: 5000 random vectors agree with the model.")
