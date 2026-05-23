---
layout: default
title: FPGA
permalink: /fpga/
---

# FPGA implementation

I targeted a Xilinx Zynq-7000 on a Digilent PYNQ-Z2 board for hardware bring-up. This page documents what synthesis cost, where the timing closed, where the design sat on the fabric, and the live demo running on the board. The bug from bring-up moved to the [Verification]({{ '/verification/' | relative_url }}#postmortems) postmortems, where it shares context with the rest of the verification work.

{% include results-strip.html %}

## Toolchain and target {#target}

- Target board: {{ site.results.fpga_target }}
- Toolchain: {{ site.results.toolchain }}
- Top module: [`src/pynq_z2_top.sv`](https://github.com/cshieldsce/riscv-5/blob/main/src/pynq_z2_top.sv)
- Clock target: {{ site.results.clock_target_mhz }} MHz (period {{ site.results.clock_target_period_ns }} ns, closed with positive slack)

## Resource utilization {#utilization}

The full RV32I core, register file, instruction and data memories, MMIO, and the PYNQ-Z2 top-level fit comfortably in the Zynq-7000 with substantial headroom for future extensions (caches, additional MMIO, peripherals).

<div class="img-wrapper screenshot">
  <img src="{{ '/images/vivado-utilization-table.png' | relative_url }}" alt="Vivado utilization table summarizing LUTs, flip-flops, and BRAM usage on the Zynq-7000">
  <span class="caption">Vivado post-implementation utilization for the full design.</span>
</div>

<div class="img-wrapper screenshot">
  <img src="{{ '/images/vivado-utilization-graph.png' | relative_url }}" alt="Vivado utilization graph broken out by module hierarchy">
  <span class="caption">Same utilization, broken out by module hierarchy: the register file and ALU dominate, the memories are small.</span>
</div>

## Timing closure {#timing}

The clock was constrained to {{ site.results.clock_target_period_ns }} ns ({{ site.results.clock_target_mhz }} MHz). At that target Vivado closes with positive worst-negative-slack across all paths; the timing summary below is the post-implementation report.

<div class="img-wrapper screenshot">
  <img src="{{ '/images/vivado-design-timing-summary.png' | relative_url }}" alt="Vivado design timing summary showing met setup, hold, and pulse-width with positive worst-negative-slack">
  <span class="caption">Setup, hold, and pulse-width all met at {{ site.results.clock_target_mhz }} MHz.</span>
</div>

Fmax is open. The {{ site.results.clock_target_mhz }} MHz constraint was deliberately conservative for bring-up; rerunning synthesis with the constraint loosened (or removed) and reading the resulting WNS would let me quote a real maximum. That's a TODO; until I do, the [results strip]({{ '/' | relative_url }}#what-works-today) keeps `fmax_mhz` hidden.

## Implementation layout {#layout}

The placed-and-routed design on the Zynq-7000 fabric, captured from the Vivado device view. The placement is sparse, which is the visual confirmation of the utilization numbers above.

<div class="img-wrapper screenshot">
  <img src="{{ '/images/vivado-implementation-device.png' | relative_url }}" alt="Vivado implementation device view: placed cells on the Zynq-7000 FPGA fabric, with most of the device unused">
  <span class="caption">Post-implementation placement on the Zynq-7000 fabric. The lit-up region shows the riscv-5 core; the rest of the device is unused.</span>
</div>

## Lessons from bring-up {#lessons}

Two pieces of advice I would give myself if I were starting again:

1. **Use the Xilinx Clocking Wizard for any non-trivial clock.** The first revision of the PYNQ-Z2 top-level used a small logic-based clock divider to derive the CPU clock from the board's 125 MHz reference. That worked in simulation, but on the board the JTAG debug hub became unstable and the ILA dropped triggers intermittently. Switching to a Clocking Wizard IP block stabilized the clock tree, fixed the JTAG flakiness, and made the ILA reliable. Worth the IP-block bureaucracy.
2. **Memory timing is the first thing to verify on real hardware.** The bug documented in the [postmortem]({{ '/verification/' | relative_url }}#bouncing-branch) was a sim-vs-synth mismatch: the simulation model of the instruction memory was combinational, the FPGA implementation used synchronous block RAM. The pipeline's IF stage assumes single-cycle fetch, and that assumption only failed on the board. Anything that simulates one way and synthesizes another deserves an explicit equivalence check before bring-up.

## Hardware demo {#demo}

`src/pynq_z2_top.sv` wires the lower four bits of the MMIO LED register at `0x8000_0000` to the board's four user LEDs. Any RISC-V program that writes to that address shows up on the LEDs the next cycle. The demo program is a Fibonacci generator that writes successive terms; because the LEDs are four bits, values larger than 15 wrap modulo 16, so the visible sequence rolls over after `13 → 21 → 34`.

```bash
Sequence Displayed on LEDs:
  * 1  -> 0001 (1)
  * 2  -> 0010 (2)
  * 3  -> 0011 (3)
  * 5  -> 0101 (5)
  * 8  -> 1000 (8)
  * 13 -> 1101 (13)
  * 21 -> 0101 (5)  (21 is 10101 binary; bottom 4 bits are 0101)
  * 34 -> 0010 (2)  (34 is 100010 binary; bottom 4 bits are 0010)
```

<video controls src="{{ '/images/fpga-fib-test-demo.mp4' | relative_url }}" width="480"></video>

A short video of the program running on the board. The same Fibonacci binary that produces this sequence on hardware also passes its [regression testbench]({{ '/verification/' | relative_url }}#riscof) in simulation.

## Reproducing the build {#reproduce}

- Bitstream and synthesis scripts live under [`fpga/`](https://github.com/cshieldsce/riscv-5/tree/main/fpga) in the repo.
- The Fibonacci hex image used above: [`test/mem/fib_test.mem`](https://github.com/cshieldsce/riscv-5/blob/main/test/mem/fib_test.mem).
- End-to-end build steps (Vivado project generation, bitstream, board flash): [Setup]({{ '/setup/' | relative_url }}#fpga-deployment).
