---
layout: default
title: Architecture
sidebar: architecture
permalink: /architecture/
---

# Architecture overview

The `riscv-5` core is a classic Patterson & Hennessy 5-stage RV32I pipeline: instruction fetch, decode, execute, memory access, and writeback, separated by pipeline registers. This page is the overview. [Pipeline Stages]({{ '/architecture/stages/' | relative_url }}) walks through each stage with the actual SystemVerilog. [Hazards & Forwarding]({{ '/architecture/hazards/' | relative_url }}) covers how I keep the pipeline correct under data and control hazards.

I leaned on two references throughout the project: the RISC-V unprivileged ISA specification, and *Computer Organization and Design: The Hardware/Software Interface (RISC-V Edition)* by Patterson & Hennessy, especially chapter 4. Specific section pointers are in the [References](#references) list at the bottom.

## Why pipeline at all {#why-pipeline}

A single-cycle CPU fetches, decodes, executes, accesses memory, and writes back in one clock tick. Every instruction takes one clock, but every clock has to be long enough for the signal to propagate through the entire datapath end to end. The critical path is the full datapath, which fails timing closure well before useful FPGA frequencies.

Pipelining splits that long critical path into shorter stages separated by registers. The clock period only has to cover the longest single stage rather than the whole datapath. Latency for one instruction stays roughly the same (technically slightly worse, because of the register overhead between stages), but throughput climbs because a new instruction enters the pipeline every cycle.

<div class="callout tip"><span class="title">Where this shows up in Vivado</span>
In a single-cycle design, Vivado's <strong>Total Negative Slack (TNS)</strong> report will flag a long combinational path from instruction memory to register-file writeback as the critical path. Pipelining is the architectural fix: the pipeline registers chop that path into segments and each segment closes timing independently.
</div>

<div class="callout warn"><span class="title">Latency vs. throughput</span>
Pipelining does not make a single instruction finish faster. The latency from "instruction enters fetch" to "result written back" is the same five cycles (or worse, given the register overhead between stages). The win is throughput: in steady state, one instruction completes every cycle, so we trade one instruction's latency for N instructions' throughput.
</div>

## The datapath {#datapath}

<div class="img-wrapper diagram">
  <img src="{{ '/images/pipeline_stages_clean.svg' | relative_url }}" alt="Five-stage pipelined RISC-V datapath: IF, ID, EX, MEM, WB separated by pipeline registers">
  <span class="caption">Figure 1: The conceptual 5-stage RISC-V datapath. Each labelled box is one stage; the vertical bars between them are pipeline registers that hand state to the next stage on every clock edge.</span>
</div>

<div class="img-wrapper diagram">
  <img src="{{ '/images/pipeline_basic.png' | relative_url }}" alt="Block-level view of the riscv-5 datapath showing the components per stage">
  <span class="caption">Figure 2: The same datapath with the major blocks per stage (PC + instruction memory in IF, register file + control in ID, ALU in EX, data memory in MEM, writeback mux in WB).</span>
</div>

These two figures are the conceptual reference. The [Pipeline Stages]({{ '/architecture/stages/' | relative_url }}) page replaces the boxes with the actual SystemVerilog: the PC-mux priority order, the instruction-field decode, the ALU source multiplexers, the forwarding paths into EX, the byte-enable generation for sub-word loads and stores, and the writeback mux.

## What the core does and doesn't do {#scope}

`riscv-5` implements the RV32I base integer ISA: arithmetic, logical, shifts, comparisons, loads and stores (including the byte and half-word variants with sign- or zero-extension), unconditional branches (JAL, JALR), and the six conditional branches (BEQ, BNE, BLT, BGE, BLTU, BGEU). LUI and AUIPC route through the ALU using small tricks documented on the [Stages]({{ '/architecture/stages/' | relative_url }}) page.

It does **not** implement the M extension (no hardware multiply or divide), any CSRs (the `SYSTEM` and `FENCE` opcodes both decode as NOPs in [`src/control_unit.sv`](https://github.com/cshieldsce/riscv-5/blob/main/src/control_unit.sv)), any cache, or exception or interrupt handling. Test completion is signaled by a memory-mapped `tohost` address at `0x8000_1000` that the simulation harness watches; on the FPGA, the 4-bit memory-mapped LED register at `0x8000_0000` is the only I/O.

## References {#references}

1. Patterson, D. A. & Hennessy, J. L. *Computer Organization and Design: The Hardware/Software Interface (RISC-V Edition).* Morgan Kaufmann, 2017.
   - Chapter 4: the processor and the 5-stage pipeline
   - Section 4.6: pipelined datapath and control
   - Section 4.7: data hazards and forwarding
   - Section 4.8: control hazards
2. RISC-V International. *The RISC-V Instruction Set Manual, Volume I: Unprivileged ISA* (v20191213).
   - Section 2: RV32I base integer instruction set
   - Section 2.5: control transfer instructions
   - Section 2.6: load and store instructions
3. RISC-V software tools: `riscv64-unknown-elf-gcc` (cross-compiler) and `spike` (golden simulator used by RISCOF).
