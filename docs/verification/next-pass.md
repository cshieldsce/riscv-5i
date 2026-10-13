---
layout: default
title: Verification next pass
permalink: /verification/next-pass/
---

# Verification next pass: design note

Written before the code. It covers what this pass adds on top of the RISCOF run and the ALU/HazardUnit cocotb benches, and why each piece is shaped the way it is. Results go in [Results](#results) once the work has run.

## Gaps this pass closes

1. RISCOF needs Spike, which takes a long time to build, so nobody runs compliance on a laptop and the pass/fail data is only a HTML report in a CI artifact.
2. The cocotb benches check the ALU and the HazardUnit in isolation. Nothing checks the forwarding unit or the register file, and nothing measures whether the *whole pipeline* ever hits the hazard and forwarding cases the unit benches assume.
3. Nothing proves properties for all inputs (x0 never forwarded, a double hazard picks EX/MEM, and so on). Random tests only sample them.
4. CI runs cocotb on Icarus only.

## What gets added

### 1. RV32I compliance in simulation, with a pass/fail table

- `test/cocotb/rv32i_ref.py`: a small RV32I instruction-set simulator plus an instruction encoder. It is the reference model, so the compliance run does not need Spike. It is also the oracle for the random-program test below.
- `test/cocotb/build_compliance.py`: builds each `riscv-arch-test` RV32I test with the same compiler flags, linker script and `model_test.h` the RISCOF plugin uses, and converts the ELF to hex with the existing `elf2hex.py`. The suite is pinned to tag `3.9.1`, the last one with the `rv32i_m/I/src` layout the plugin expects.
- `test/cocotb/test_compliance.py`: runs each hex image on the real `PipelinedCPU` with the real `InstructionMemory` and `DataMemory`, stops on the `tohost` write, takes the signature region, and compares it to the signature the ISS produced. One row per test goes to `results_compliance.md`.

The reference is a model I wrote, so it is weaker evidence than Spike. I keep RISCOF as the authoritative run and use this one as a quick local check, with the ISS itself unit-tested against hand-encoded instructions and the spec's corner cases. The results page says which run is which.

Without the arch-test checkout or a RISC-V gcc the compliance test **skips** with a message instead of failing, so `make` still passes offline.

### 2. Pipeline functional coverage

`test/cocotb/cpu_tb_top.sv` wraps the CPU and the two memories (same wiring as `test/tb/pipelined_cpu_tb.sv`) so cocotb can drive it. RTL under `src/` is not touched.

`test_pipeline_coverage.py` runs directed programs built with the encoder, plus random programs checked against the ISS. Every cycle it samples internal signals into `funcov.Cross` bins:

| Cross | Axes |
|---|---|
| forwarding source | operand (A, B) x source (register file, EX/MEM, MEM/WB) |
| forwarding producer | source (EX/MEM, MEM/WB) x producer class (ALU, load, JAL/JALR link, LUI/AUIPC) |
| double hazard | both stages write the same register, EX/MEM must win |
| x0 and no-write | rd = x0, or reg_write = 0, never forwards |
| hazard event | load-use stall, ALU-to-branch stall, taken branch, JALR, JAL |
| store data | store whose rs2 comes from EX/MEM, MEM/WB or the register file |
| register file | WB-to-ID write-through hit |

The test fails if a reachable bin is never hit, as in the existing benches. Final architectural state of every directed program is checked against the ISS, so coverage is only counted for runs that were also correct.

### 3. Formal checks (SymbiYosys)

`formal/` holds one `.sby` file and one property wrapper per block. The wrappers instantiate the unmodified RTL:

- ForwardingUnit: forward is `00` whenever rs is x0 or the producer isn't writing; EX/MEM wins over MEM/WB; MEM/WB is chosen only if EX/MEM doesn't match; the output is never `11`; and the output matches a restated spec. It's combinational, so a bounded check of depth 1 covers all inputs.
- RegFile: x0 reads zero, write-through hits the same cycle, a write is visible one cycle later, and a write to one register doesn't change another (a free address chosen with `$anyconst`).

Toolchain: Yosys, `sby`, and an SMT solver (z3 or boolector). If any is missing the workflow step is skipped locally; CI installs them. Each property has a mutation I ran by hand to confirm the check can fail (listed in the results).

### 4. CI

New jobs in `.github/workflows/ci.yml`:

- `cocotb-icarus`: the full cocotb suite on Icarus (replaces the current two-step job).
- `cocotb-verilator`: the same suite on Verilator. cocotb 2.x needs 5.036+, which Ubuntu's apt doesn't have, so it's built from the release tag and cached.
- `formal`: SymbiYosys runs.
- `compliance-sim`: checks out arch-test at the pinned tag, installs the gcc, runs the compliance test and uploads the table.

The existing RISCOF workflow stays as it is.

## Test strategy

- Pure Python (ISS, encoder, table writer) is covered by `pytest`, no simulator needed.
- cocotb tests use Python memories or the real RTL memories; no network, Docker or GPU. Only fetching arch-test needs the network, and that is optional.
- Test first: ISS and encoder tests were written against the spec before the model; the coverage test goes red on a deliberately removed forwarding path before it's accepted.

## Results {#results}

See the end of this page after the run (filled in once the numbers exist).
