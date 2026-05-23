---
layout: default
title: Verification
permalink: /verification/
---

# Verification

I verified `riscv-5` against the [RISCOF](https://riscof.readthedocs.io/) compliance suite and a hand-written regression set, and validated the live core on a PYNQ-Z2 with a Vivado ILA. This page covers both: the compliance matrix at the top, and one substantive postmortem at the bottom from the FPGA bring-up.

{% include results-strip.html %}

## RISCOF compliance {#riscof}

RISCOF runs the [official RISC-V architectural test suite](https://github.com/riscv-non-isa/riscv-arch-test) against the core under test and the [Spike](https://github.com/riscv-software-src/riscv-isa-sim) reference simulator side by side. Each test produces a signature, the two signatures are diffed, and a test passes only if the bytes match exactly. The core has no leeway to "almost" implement an instruction; the byte diff catches subtle bugs that a self-test loop would miss.

The DUT and golden-model plugins for this project live under [`test/verification/compliance/`](https://github.com/cshieldsce/riscv-5/tree/main/test/verification/compliance), and the runner is [`run_compliance.sh`](https://github.com/cshieldsce/riscv-5/blob/main/test/verification/compliance/run_compliance.sh).

### Compliance matrix {#matrix}

| ISA | Test suite | Tests pass | Of total | Golden model |
| :--- | :--- | ---: | ---: | :--- |
| **RV32I** | `riscv-arch-test` | {{ site.results.riscof_rv32i_pass }} | {{ site.results.riscof_rv32i_total }} | `{{ site.results.riscof_golden_model | downcase }}` |
| **Regression** | hand-written `*_tb.sv` | {{ site.results.riscof_regression_pass }} | {{ site.results.riscof_regression_total }} | `{{ site.results.riscof_golden_model | downcase }}` |

### Continuous integration {#ci}

Every push to `main` triggers the full RISCOF suite and the regression testbenches via GitHub Actions. The badges below reflect the current status of `main`.

<div class="callout note"><span class="title">CI status</span>
<ul>
  <li><strong>Regression:</strong> <a href="https://github.com/cshieldsce/riscv-5/actions/workflows/ci.yml"><img src="https://github.com/cshieldsce/riscv-5/actions/workflows/ci.yml/badge.svg" alt="CI Status"></a></li>
  <li><strong>Compliance:</strong> <a href="https://github.com/cshieldsce/riscv-5/actions/workflows/compliance.yml"><img src="https://github.com/cshieldsce/riscv-5/actions/workflows/compliance.yml/badge.svg" alt="Compliance Status"></a></li>
</ul>
</div>

In addition to RISCOF, I wrote two SystemVerilog testbenches that exercise specific microarchitectural behavior the compliance suite doesn't directly target: [`test/tb/pipelined_cpu_tb.sv`](https://github.com/cshieldsce/riscv-5/blob/main/test/tb/pipelined_cpu_tb.sv) walks structured instruction sequences through every forwarding and stall case, and [`test/tb/fib_test_tb.sv`](https://github.com/cshieldsce/riscv-5/blob/main/test/tb/fib_test_tb.sv) runs a Fibonacci program end-to-end (the same program that drives the FPGA demo).

## Postmortems {#postmortems}

### The bouncing branch {#bouncing-branch}

The first time I brought the core up on the PYNQ-Z2, branches looked broken. A test program that should have lit the LEDs with the binary value `0010` (decimal 2) lit them with `0101` (decimal 5) instead. RISCOF in simulation was passing every test; on the board the same code took the wrong path.

**Symptom.** A program with a single conditional branch that should have skipped over a "failure" sequence didn't skip. The LEDs displayed the value the registers held before the branch would have fired, suggesting the processor was effectively executing NOPs in place of the branch.

**Diagnosis.** I dropped in a Vivado ILA and triggered on the program counter reaching the branch's PC. The capture below shows the bug: the PC steps to `0x30` (the branch instruction), but the `Instruction` bus still shows `00000013` (a NOP), and `branch_en`/`branch_taken` stay low. The instruction the pipeline thought it was decoding was a stale value from the previous cycle.

<div class="img-wrapper screenshot">
  <img src="{{ '/images/fpga_problem1.png' | relative_url }}" alt="Vivado ILA waveform: PC=0x30 with branch_en=0 and Instruction=NOP, one cycle behind where it should be">
  <span class="caption">ILA capture before the fix. PC has advanced to the branch but the instruction bus is still showing the previous cycle's value, and the branch never fires.</span>
</div>

**Root cause.** The instruction memory was originally written as a synchronous block-RAM: a clocked `always_ff` that latches the addressed word on the next clock edge. In a 5-stage pipeline that assumes a single-cycle fetch, that one-cycle latency is a half-step out of phase. Each cycle the IF/ID register sampled the data the memory had produced *last* cycle (for the previous PC), so every instruction was effectively shifted one slot late. Branches, which compute their target from values current in EX, decoded the wrong instruction and never fired.

```verilog
// Old: synchronous read. Data ready on the NEXT clock edge,
// which is one cycle too late for IF/ID to latch the right word.
always_ff @(posedge clk) begin
    if (en) begin
        Instruction <= (word_addr < 4096) ? rom_memory[word_addr] : 32'h00000013;
    end
end
```

**Fix.** I rewrote `src/instruction_memory.sv` as a combinational read so the addressed word appears on the bus the same cycle the address is presented. On the FPGA this synthesizes to distributed LUTRAM (which is fine for the 16 KB instruction store this design uses) rather than block RAM.

```verilog
// New: combinational read. The instruction is on the bus the same cycle
// the address is, which is what IF/ID expects.
// Source: src/instruction_memory.sv
assign word_addr   = Address >> 2;
assign Instruction = (word_addr < RAM_MEMORY_SIZE) ? rom_memory[word_addr] : NOP_A;
```

**Verification.** Re-ran the same test with the ILA still attached. The PC steps to `0x30`, the instruction bus updates to the actual branch opcode the same cycle, `branch_en` and `branch_taken` go high, and the PC jumps to `0x40`. The LEDs subsequently display `0010` as expected.

<div class="img-wrapper screenshot">
  <img src="{{ '/images/fpga_problem1_solved.png' | relative_url }}" alt="Vivado ILA waveform after fix: PC=0x30, branch_en=1, branch_taken=1, PC jumps to 0x40">
  <span class="caption">ILA capture after the fix. branch_taken is high on the same cycle the branch is in EX and the PC redirects to the branch target.</span>
</div>

**What I would have caught in sim.** Nothing, because the simulation model of the instruction memory was always combinational. The mismatch was specifically between sim and synth. Adding an FPGA-vs-sim equivalence check, or moving the instruction memory into RISCOF as a parameter, would have surfaced this before the board. That cross-check is on the open list for the next pass through verification infrastructure.
