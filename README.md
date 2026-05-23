# riscv-5

A 5-stage pipelined RISC-V core (RV32I) written in SystemVerilog, verified against the RISCOF compliance suite, and running on a Xilinx Zynq-7000 FPGA.

[![CI Status](https://github.com/cshieldsce/riscv-5/actions/workflows/ci.yml/badge.svg)](https://github.com/cshieldsce/riscv-5/actions/workflows/ci.yml)
[![Compliance Status](https://github.com/cshieldsce/riscv-5/actions/workflows/compliance.yml/badge.svg)](https://github.com/cshieldsce/riscv-5/actions/workflows/compliance.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-gray.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://cshieldsce.github.io/riscv-5/)

![Complete Pipelined Datapath](docs/images/pipeline_complete.svg)

## What this is

The classic Patterson & Hennessy 5-stage pipeline (IF, ID, EX, MEM, WB), with full forwarding, load-use stalling, and early branch resolution for JAL. Passes all 482 RISCOF RV32I compliance tests against Spike. Synthesizes on a PYNQ-Z2 at 10 MHz with positive slack, using 1972 LUTs (3.7% of the Zynq-7000) and 3326 flip-flops. The full design fits comfortably with room to spare for caches or peripherals.

## What's not there

I scoped this to RV32I and stopped. No M extension (no hardware multiply or divide), no CSRs (SYSTEM and FENCE decode as NOPs), no caches, no exception or interrupt handling. Memory is a single flat region with a memory-mapped LED register at `0x8000_0000` and a `tohost` test-completion address at `0x8000_1000`.

## Documentation

**[Full documentation site →](https://cshieldsce.github.io/riscv-5/)**

- [Architecture overview](https://cshieldsce.github.io/riscv-5/architecture/) — datapath, pipeline diagram, design tradeoffs
- [Pipeline stages](https://cshieldsce.github.io/riscv-5/architecture/stages/) — per-stage RTL with explanations
- [Hazards & forwarding](https://cshieldsce.github.io/riscv-5/architecture/hazards/) — timing diagrams for every hazard case
- [Verification](https://cshieldsce.github.io/riscv-5/verification/) — RISCOF results and a bring-up postmortem
- [FPGA](https://cshieldsce.github.io/riscv-5/fpga/) — synthesis numbers, timing closure, hardware demo
- [Setup](https://cshieldsce.github.io/riscv-5/setup/) — toolchain install and build instructions

## Quick start

```bash
# Install dependencies (Ubuntu/Fedora)
sudo apt-get install -y iverilog gtkwave python3-pip git gcc-riscv64-unknown-elf
pip3 install riscof

# Clone and bootstrap
git clone https://github.com/cshieldsce/riscv-5.git
cd riscv-5
./setup_project.sh

# Run the compliance suite
./test/verification/run_compliance.sh
```

Full setup instructions: [Setup page](https://cshieldsce.github.io/riscv-5/setup/).

## Project layout

```
riscv-5/
├── src/                  # SystemVerilog RTL
│   ├── pipelined_cpu.sv  # top-level CPU
│   ├── if_stage.sv       # IF, ID, EX, MEM, WB modules
│   ├── id_stage.sv
│   ├── ex_stage.sv
│   ├── mem_stage.sv
│   ├── wb_stage.sv
│   ├── control_unit.sv   # instruction decoder
│   ├── hazard_unit.sv    # stall / flush logic
│   ├── forwarding_unit.sv
│   └── pynq_z2_top.sv    # board top-level
├── test/
│   ├── verification/     # RISCOF compliance plugins + runner
│   ├── tb/               # SystemVerilog testbenches
│   ├── mem/              # .mem hex images for tests
│   └── scripts/          # lint + regression
├── fpga/                 # Vivado project scripts + XDC
└── docs/                 # Jekyll source for the docs site
```

## References

- [RISC-V Unprivileged ISA Specification](https://riscv.org/technical/specifications/) (v20191213)
- Patterson & Hennessy, *Computer Organization and Design: The Hardware/Software Interface (RISC-V Edition)*, chapter 4
- [RISC-V Architectural Test Suite](https://github.com/riscv-non-isa/riscv-arch-test)

## License

MIT — see [LICENSE](LICENSE).
