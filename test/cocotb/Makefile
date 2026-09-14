# Makefile for the cocotb testbenches
#
# Usage:
#   make alu               # ALU testbench
#   make hazard            # HazardUnit testbench
#   make coverage          # Line coverage report (Verilator only)
#   make alu SIM=icarus    # Same tests on Icarus Verilog (what CI runs)
#
# Needs cocotb 2.x (pip install cocotb) and Verilator 5.036+ or Icarus 12.

SIM ?= verilator
TOPLEVEL_LANG ?= verilog
RTL_DIR := $(abspath ../../src)

# Verilator writes line coverage while the tests run, one file per testbench
ifeq ($(SIM),verilator)
    EXTRA_ARGS += --coverage -Wno-fatal
    PLUSARGS += +verilator+coverage+file+coverage_$(BENCH).dat
endif

ifeq ($(BENCH),hazard)
    TOPLEVEL = HazardUnit
    COCOTB_TEST_MODULES = test_hazard_unit
    VERILOG_SOURCES = $(RTL_DIR)/riscv_pkg.sv $(RTL_DIR)/hazard_unit.sv
else
    TOPLEVEL = ALU
    COCOTB_TEST_MODULES = test_alu
    VERILOG_SOURCES = $(RTL_DIR)/riscv_pkg.sv $(RTL_DIR)/alu.sv
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: alu hazard coverage

alu:
	$(MAKE) BENCH=alu SIM_BUILD=sim_build_alu COCOTB_RESULTS_FILE=results_alu.xml

hazard:
	$(MAKE) BENCH=hazard SIM_BUILD=sim_build_hazard COCOTB_RESULTS_FILE=results_hazard.xml

coverage:
	@mkdir -p coverage
	@for bench in alu hazard; do \
		if [ -f coverage_$$bench.dat ]; then \
			echo "[*] Line coverage for $$bench:"; \
			verilator_coverage --annotate coverage/$$bench --annotate-all coverage_$$bench.dat | tail -1; \
		else \
			echo "[!] WARNING: No coverage_$$bench.dat, run 'make $$bench' first."; \
		fi; \
	done
