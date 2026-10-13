# cocotb testbenches

RISCOF tells me the core runs every RV32I instruction correctly, but it's directed testing at the ISA level. When a compliance test fails it doesn't say much about which unit broke or which input did it. So I added unit-level testbenches for the two blocks with the most corner cases: the ALU and the hazard unit. A later pass added whole-pipeline coverage, a compliance run in simulation and formal checks, described under [Pipeline coverage](#pipeline-coverage), [Compliance in simulation](#compliance-in-simulation) and [Formal](#formal). Both use random stimulus, check every output against a Python model, and track functional coverage so I can see which cases never got hit.

## Running them

```bash
pip install cocotb
cd test/cocotb
make alu          # ALU testbench
make hazard       # HazardUnit testbench
make pipeline     # whole-pipeline hazard and forwarding coverage
make ref          # pytest checks for the encoder and the reference ISS
make compliance ARCH_TEST=<riscv-arch-test 3.9.1 checkout>
make coverage     # Verilator line coverage, written to coverage/
```

The default simulator is Verilator (5.036 or newer, which cocotb 2.x needs). `make alu SIM=icarus` runs the same tests on Icarus Verilog 12, which is what CI uses. Icarus doesn't give line coverage.

## ALU

`test_alu.py` has a Python model of the ALU and three tests:

1. Every op against every pair of operand classes. The classes are zero, all ones, `0x7FFF_FFFF`, `0x8000_0000`, a small number and a random number, so 10 ops x 6 x 6 gives 360 bins. After that it runs all 32 shift amounts for SLL, SRL and SRA with junk in the upper bits of B, since the shifter should only look at the low 5 bits.
2. 4000 random ops, with operands pulled from the same classes.
3. The 6 ALUControl codes nothing uses, which should all output 0.

## Hazard unit

`test_hazard_unit.py` models the same priority chain as `hazard_unit.sv`: load-use first, then ALU-to-branch, then a taken branch or JALR, then JAL. The directed test drives every hazard type through every way the registers can line up (rd matches rs1, rs2, both, rd is x0, or no match). The lower priority inputs get set randomly too, so what it's really checking is the priority order. Then 5000 random vectors.

Four of the 25 bins can't happen. A load-use or ALU-to-branch hazard needs rd to match a source register, so the x0 and no match cases can never produce one. The test skips those on purpose instead of counting them as misses.

## Coverage helper

`funcov.py` counts coverage bins. cocotb doesn't come with one, and I didn't want another dependency for two testbenches. It counts hits for every combination of a few named axes and prints the bins that never got hit. A test fails if any reachable bin is missed.

## Pipeline coverage

`test_pipeline_coverage.py` drives the whole `PipelinedCPU` (wrapped by `cpu_tb_top.sv` with the real instruction and data memories). Directed and random programs are built with the encoder in `rv32i_ref.py` and run on the CPU and on the reference ISS. The final registers and a data window have to match, and every cycle a sampler checks both forwarding selects against a Python model and fills bins for forwarding source, producer class, double hazards, x0 and no-write cases, stall kinds, control hazards, store data and register file write-through. The last test fails if a reachable bin was never hit. The bins and results are in [docs/verification/next-pass.md](../../docs/verification/next-pass.md).

## Compliance in simulation

`build_compliance.py` compiles the riscv-arch-test 3.9.1 `rv32i_m/I` tests (`compliance_env/` has the target header and linker script), runs them on the ISS and writes the expected signatures. `test_compliance.py` runs the same images on the RTL and writes a pass/fail table to `results_compliance.md`. Without a built suite it skips. Tests that fail on a known RTL bug are listed in `compliance_known_failures.txt` and show as XFAIL.

## Formal

`../../formal/` has SymbiYosys checks for the forwarding unit and the register file. Run `formal/run.sh` from the repo root.

## Results

| Testbench | Tests | Functional coverage | Line coverage |
|---|---|---|---|
| ALU | 3/3 pass | 456/456 bins | 100% |
| HazardUnit | 2/2 pass | 21/25 bins (all 21 reachable) | 100% |
| Pipeline | 5/5 pass | all reachable bins in 8 crosses | 80% of the whole CPU |
| Compliance | 37/39 pass, 2 known failures | n/a | n/a |

To make sure the tests can actually catch a bug, I changed `>>>` to `>>` in the SRA case of `alu.sv`. Two of the three ALU tests failed and `make` exited with an error, so CI would have caught it.
