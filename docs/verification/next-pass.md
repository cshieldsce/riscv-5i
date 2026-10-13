---
layout: default
title: Verification next pass
permalink: /verification/next-pass/
---

# Verification next pass: design note

Written before the code. It covers what this pass adds on top of the RISCOF run and the ALU/HazardUnit cocotb benches, and why each piece is shaped the way it is. What changed from the plan and the results are at the end, under [Changes from the plan](#changes) and [Results](#results).

## Gaps this pass closes

1. RISCOF needs Spike, which takes a long time to build, so compliance is hard to run on a laptop and the pass/fail data is an HTML report in a CI artifact.
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

## Changes from the plan {#changes}

- **Formal property wrappers are plain Verilog, not SystemVerilog.** Yosys 0.33 (what Ubuntu ships) can't read the `import riscv_pkg::*;` at the top of the RTL files, so the RTL goes through `sv2v` first, the same step `asic/convert.sh` already uses. `sv2v` silently drops `assert` and `cover`, which made my first set of proofs vacuous (every mutation survived). The properties now live in `formal/*_props.v`, which Yosys reads directly. `formal/run.sh` does the conversion and runs `sby`.
- **RegFile uses ABC `bmc3` at depth 4**, not z3. z3 spent over a minute on step 2 of the 32x32 memory and I stopped it. It is a bounded check rather than a proof, and has no cover task for the same reason.
- **The compliance image is built to JSON** (`build_compliance.py` runs the ISS too), so the cocotb side needs no RISC-V toolchain. The ELF is read by a small parser in `build_compliance.py`, not `elf2hex.py`: the link script puts `.tohost` at `0x8000_1000` and `objcopy -O binary` would pad the binary out to about 2 GB to reach it.
- **`test/cocotb/compliance_env/`** has its own `model_test.h` and `link.ld`. The ones under `test/verification/compliance/` were written for an older arch-test layout; with 3.9.1 they define `_start` twice. The RISCOF files are untouched.
- Known-failure handling (`compliance_known_failures.txt`) was added once the first run found a real RTL failure, see below.

## Results {#results}

Run on Icarus Verilog 12.0 and Verilator 5.036 with cocotb 2.1.0, Yosys 0.33, `sby` tag `yosys-0.33`, z3 4.8.12, sv2v 0.0.13, `riscv64-unknown-elf-gcc` and riscv-arch-test `3.9.1`. Everything passes with no network once arch-test has been cloned.

| Check | Command (in `test/cocotb` unless noted) | Result |
|---|---|---|
| Encoder and ISS | `make ref` | 30 pass |
| ALU | `make alu` | 3/3 pass (Icarus, Verilator) |
| HazardUnit | `make hazard` | 2/2 pass (Icarus, Verilator) |
| Pipeline coverage | `make pipeline` | 5/5 pass (Icarus, Verilator), 161 directed and 150 random programs match the ISS |
| RV32I compliance in simulation | `make compliance ARCH_TEST=<3.9.1 checkout>` | 37/39 pass, 2 known failures (below) |
| Formal | `formal/run.sh` | ForwardingUnit proven by k-induction (and covers reached), RegFile bounded to 4 steps, both pass |

### RV32I compliance, pass/fail table {#compliance}

Each test is the `rv32i_m/I` program from riscv-arch-test 3.9.1. The signature the RTL leaves in memory is compared word for word with the one the reference ISS produces. This is **not** the Spike comparison the RISCOF run does: the reference here is `rv32i_ref.py`, which I wrote and unit-tested against GNU assembler output, so it is evidence for the RTL only as far as that model is right.

| Test | Result | Signature words | Cycles |
|---|---|---:|---:|
| add-01 | PASS | 592 | 3269 |
| addi-01 | PASS | 564 | 2196 |
| and-01 | PASS | 588 | 3234 |
| andi-01 | PASS | 564 | 2200 |
| auipc-01 | PASS | 68 | 437 |
| beq-01 | PASS | 588 | 6783 |
| bge-01 | PASS | 592 | 7418 |
| bgeu-01 | PASS | 728 | 9063 |
| blt-01 | PASS | 584 | 7242 |
| bltu-01 | PASS | 728 | 9007 |
| bne-01 | PASS | 588 | 7860 |
| fence-01 | PASS | 4 | 119 |
| jal-01 | PASS | 36 | 1694 |
| jalr-01 | PASS | 36 | 1144 |
| lb-align-01 | PASS | 36 | 634 |
| lbu-align-01 | PASS | 36 | 618 |
| lh-align-01 | PASS | 36 | 618 |
| lhu-align-01 | PASS | 36 | 618 |
| lui-01 | PASS | 68 | 242 |
| lw-align-01 | PASS | 36 | 618 |
| misalign1-jalr-01 | PASS | 4 | 136 |
| or-01 | PASS | 592 | 3268 |
| ori-01 | PASS | 564 | 2186 |
| **sb-align-01** | **FAIL (known)** | 72 | 628 |
| **sh-align-01** | **FAIL (known)** | 76 | 632 |
| sll-01 | PASS | 92 | 511 |
| slli-01 | PASS | 92 | 417 |
| slt-01 | PASS | 588 | 3255 |
| slti-01 | PASS | 564 | 2189 |
| sltiu-01 | PASS | 704 | 2673 |
| sltu-01 | PASS | 724 | 3933 |
| sra-01 | PASS | 92 | 513 |
| srai-01 | PASS | 92 | 412 |
| srl-01 | PASS | 96 | 534 |
| srli-01 | PASS | 92 | 421 |
| sub-01 | PASS | 596 | 3280 |
| sw-align-01 | PASS | 72 | 611 |
| xor-01 | PASS | 592 | 3264 |
| xori-01 | PASS | 568 | 2210 |

**37/39 pass.** Only the `I` directory is run; the other extension directories in that suite need CSRs, traps or other extensions this core doesn't have.

### Known failures: SB and SH to a non-zero byte offset {#known-failures}

`sb-align-01` and `sh-align-01` fail, and the cause is in the RTL, not the harness. For `sb x?, 2(...)` the traced signals at the data memory are:

```
dmem_addr = 0x0020101a   dmem_wdata = 0x00400000   dmem_be = 0100
```

`mem_stage.sv` picks the byte-enable lane from the address but passes `rs2` through unshifted, and `data_memory.sv` writes `WriteData[8*i +: 8]` into lane `i`. So the byte at address offset 2 gets rs2 bits 23:16 (here `0x40`) instead of bits 7:0 (`0x00`). SH to offset 2 does the same with bits 31:16. Stores at offset 0 are right, which is why `sw-align-01` and the random programs (restricted to offset 0 for SB/SH) pass. The fix is to shift `dmem_wdata` left by `8 * addr[1:0]` for SB and SH in `mem_stage.sv`. I did not change the RTL in this pass. The two tests are listed in `test/cocotb/compliance_known_failures.txt` so the run shows them as XFAIL and stays green, and goes red (XPASS) once someone fixes the bug and forgets to delete the entries.

I could not check this against Spike here (no Spike build in this environment), so the existing RISCOF run is where to confirm it. If RISCOF passes these two tests, the plugin build differs from this one in a way worth understanding.

Two smaller observations while reading the path: `data_memory.sv` defines `handle_tohost_write` but nothing calls it, so the existing `pipelined_cpu_tb.sv` flow never writes `signature.txt` (the cocotb run detects the tohost store from the CPU's memory port instead); and a store to `0x8000_1000` also aliases into RAM word `0x400` because the memory only decodes the low 22 address bits.

### Pipeline functional coverage {#coverage}

`make pipeline` (140 producer/consumer programs, 12 special forwarding cases, 9 control-flow programs, 150 random programs). Every program's final registers and the data window are compared with the ISS, and every cycle the sampler also compares both forwarding selects with a Python model.

| Cross | Bins hit | Notes |
|---|---:|---|
| forwarding source (A/B x reg, EX/MEM, MEM/WB) | 6/6 | |
| forwarding producer (source x ALU, load, link) | 4/4 reachable | EX/MEM x load and EX/MEM x link can't happen; the test asserts they never do |
| double hazard (A, B) | 2/2 | EX/MEM wins |
| no forward despite rd match (x0 and no-write, both stages, A/B) | 8/8 | |
| stall kind x consumer operand (load-use, ALU-branch x rs1, rs2, both) | 6/6 | |
| control hazard (taken branch, JALR, JAL) | 3/3 | flush signals asserted per event |
| store data source (register, EX/MEM, MEM/WB, MEM-stage WB) | 4/4 | |
| register file write-through (rs1, rs2) | 2/2 | |

Verilator line coverage of the whole CPU under this bench is 451/559 (80%). `forwarding_unit`, `hazard_unit`, `id_stage`, `if_stage`, `imm_gen` and `pipeline_reg` are at 100%. What's left is mostly `data_memory` (tohost task and unaligned paths) and the SB/SH offsets the random test avoids.

**Finding: the store-data forward in the MEM stage is redundant.** `mem_stage.sv` forwards WB data into a store that is in MEM. The sampler sees that condition hold, but replacing it with `1'b0` leaves all five tests passing, because the EX-stage forwarding has already supplied the same value. It costs a mux and a comparator and could be removed, or kept as a belt-and-braces path; I left it alone.

### Mutation checks {#mutations}

To make sure the checks can fail, each change below was made by hand to `src/`, the check run, and the change reverted.

| Mutation | `make pipeline` | `formal/run.sh` |
|---|---|---|
| `forwarding_unit`: drop the double-hazard guard | fails | fails |
| `forwarding_unit`: forward from MEM/WB into B never | fails | n/a |
| `forwarding_unit`: forward from x0 | fails | fails |
| `forwarding_unit`: ignore reg_write | n/a | fails |
| `forwarding_unit`: swap the EX/MEM select code | n/a | fails |
| `reg_file`: no write-through | fails | fails |
| `reg_file`: write to the wrong register | n/a | fails |
| `reg_file`: no reset | n/a | fails |
| `reg_file`: write value off by one | n/a | fails |
| `reg_file`: allow writes to x0 | n/a | survives: equivalent mutant, reads of x0 are hardwired to zero |
| `hazard_unit`: load-use detection off | fails | n/a |
| `mem_stage`: drop the MEM-stage store forward | survives (redundant path, see above) | n/a |

## Running it {#running}

```bash
cd test/cocotb
pip install "cocotb~=2.1" pytest
make ref                                  # encoder and ISS, pure Python
make pipeline SIM=icarus                  # hazard and forwarding coverage
git clone --branch 3.9.1 --depth 1 https://github.com/riscv-non-isa/riscv-arch-test /tmp/arch-test
make compliance ARCH_TEST=/tmp/arch-test SIM=icarus   # table in results_compliance.md
cd ../.. && formal/run.sh                 # needs sv2v, yosys, sby, z3
```

CI runs all of it in `.github/workflows/ci.yml` (`cocotb-icarus`, `cocotb-verilator`, `compliance-sim`, `formal`). The RISCOF workflow is unchanged.
