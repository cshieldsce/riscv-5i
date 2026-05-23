---
layout: default
title: riscv-5
hero: true
permalink: /
image: /images/pipeline_complete.svg
---

<section class="hero">
  <div class="hero-text">
    <h1>A 5-stage pipelined RISC-V core, verified and running on FPGA.</h1>
    <p class="lede">
      RV32I in SystemVerilog. Synthesizes on a Xilinx Zynq-7000 (PYNQ-Z2)
      and passes {{ site.results.riscof_rv32i_pass }} of {{ site.results.riscof_rv32i_total }}
      RISCOF compliance tests against the {{ site.results.riscof_golden_model }} golden model.
    </p>
    <p class="hero-links">
      <a class="primary" href="{{ '/architecture/' | relative_url }}">Architecture</a>
      <a href="{{ '/verification/' | relative_url }}">Verification</a>
      <a href="https://github.com/cshieldsce/riscv-5">Source on GitHub</a>
    </p>
  </div>
  <div class="hero-figure">
    <img src="{{ '/images/pipeline_complete.svg' | relative_url }}"
         alt="riscv-5 datapath: five pipeline stages with forwarding paths and hazard logic">
  </div>
</section>

{% include results-strip.html %}

## What I built

I built riscv-5 to learn pipelined CPU design end to end. It's an RV32I core in SystemVerilog, simulated with Icarus, verified with RISCOF against Spike, and deployed on a PYNQ-Z2.

The microarchitecture is the classic Patterson & Hennessy 5-stage pipeline (IF, ID, EX, MEM, WB) with full forwarding, load-use stalling, and early branch resolution for JAL. Every design choice in the source, from the PC-mux priority to the forwarding multiplexer to the LUI/AUIPC ALU shortcut, has a paragraph on the architecture page explaining why it is there.

## What works today

- {{ site.results.riscof_rv32i_pass }} of {{ site.results.riscof_rv32i_total }} RISCOF RV32I tests pass against {{ site.results.riscof_golden_model }}.
- {{ site.results.riscof_regression_pass }} of {{ site.results.riscof_regression_total }} regression tests pass on every commit via GitHub Actions.
- The core synthesizes on a {{ site.results.fpga_target }} at {{ site.results.clock_target_mhz }} MHz with positive slack ({{ site.results.toolchain }}).
- A Fibonacci test program produces the recognizable 1, 2, 3, 5, 8, 13, 21, 34 sequence on four LEDs on the board ([video on the FPGA page]({{ '/fpga/#demo' | relative_url }})).

## What's not there

I scoped this project to the RV32I base integer ISA and stopped there. The core does not implement the M extension (no hardware multiply or divide). It has no CSRs at all; `SYSTEM` and `FENCE` opcodes decode as NOPs, so `ecall`, `ebreak`, and the Zicsr instructions are not functional. There is no instruction or data cache, and no exception or interrupt handling.

Memory is a single flat region starting at `0x0000_0000` (4 MB in simulation, 16 KB ROM on the FPGA), with a 4-bit memory-mapped LED register at `0x8000_0000` and a `tohost` test-completion address at `0x8000_1000` that the simulation harness monitors.

## Where to go next

- [Architecture]({{ '/architecture/' | relative_url }}) walks through the datapath, each pipeline stage, and how I resolve hazards with forwarding, stalling, and flushing.
- [Verification]({{ '/verification/' | relative_url }}) shows the RISCOF compliance matrix and the postmortems, including a branch bug I tracked down with a Vivado ILA capture.
- [FPGA]({{ '/fpga/' | relative_url }}) covers synthesis on the Zynq-7000, timing closure, and the hardware demo video.
- [Setup]({{ '/setup/' | relative_url }}) is the toolchain quickstart: clone, install Icarus and RISCOF and Vivado, build, and simulate.
