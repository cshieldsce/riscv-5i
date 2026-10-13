#!/bin/bash
# run.sh: Convert the RTL with sv2v, then run SymbiYosys on each block with
# the plain-Verilog property wrapper (sv2v drops assert and cover). Needs sv2v, yosys, sby and z3 on PATH.
# Usage: ./run.sh [forwarding_unit|reg_file]   (default: both)

cd "$(dirname "$0")"
src=../src
mkdir -p build

for tool in sv2v yosys sby z3 boolector; do
    command -v $tool >/dev/null || { echo "FAILED: $tool not found on PATH."; exit 1; }
done

convert() {
    # $1 = block, $2 = rtl file, $3 = RTL top module
    sv2v --top=$3 $src/riscv_pkg.sv $src/$2 > build/$1.v || { echo "FAILED: sv2v on $1"; exit 1; }
}

status=0
run_block() {
    echo "[*] $1"
    rm -rf build/$1_*
    for task in $2; do
        sby -f -d build/$1_$task $1.sby $task || status=1
    done
}

blocks=${1:-"forwarding_unit reg_file"}
for block in $blocks; do
    case $block in
        forwarding_unit) convert forwarding_unit forwarding_unit.sv ForwardingUnit; run_block forwarding_unit "prove cover" ;;
        reg_file)        convert reg_file reg_file.sv RegFile;                      run_block reg_file "bmc" ;;
        *) echo "unknown block $block"; exit 1 ;;
    esac
done

[ $status -eq 0 ] && echo "PASSED: all formal checks." || echo "FAILED: see the sby output above."
exit $status
