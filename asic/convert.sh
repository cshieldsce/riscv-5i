#!/bin/bash
# convert.sh: Convert the SystemVerilog core into one Verilog-2005 file for the
# Sky130 flow. Yosys only has partial SystemVerilog support, so sv2v flattens
# the package, enums and always_comb blocks first. The memories and the PYNQ-Z2
# top stay out, so the block that gets hardened is PipelinedCPU with the
# instruction and data memory buses as ports.
#
# sv2v: https://github.com/zachjs/sv2v (the release binary is enough)

# Ensure we are in the script directory
cd "$(dirname "$0")"

src=../src
out=riscv_5i.v

# 1. Convert with sv2v
echo "[*] Converting SystemVerilog to Verilog-2005..."
sv_files=$(ls $src/*.sv | grep -vE "riscv_pkg|pynq_z2_top|instruction_memory|data_memory")
if ! sv2v -DSYNTHESIS --top=PipelinedCPU $src/riscv_pkg.sv $sv_files > $out; then
    echo "FAILED: sv2v could not convert the sources."
    exit 1
fi

# 2. Make sure the output still compiles as plain Verilog
echo "[*] Compiling $out with Icarus (-g2005)..."
if ! iverilog -g2005 -o /dev/null $out; then
    echo "FAILED: $out does not compile as Verilog-2005."
    exit 1
fi

# 3. Verilator lint. Warnings get printed but don't fail the script.
echo "[*] Linting $out with Verilator..."
verilator --lint-only -Wno-fatal --top-module PipelinedCPU $out

echo "PASSED: Wrote $out ($(grep -c '^module' $out) modules)."
