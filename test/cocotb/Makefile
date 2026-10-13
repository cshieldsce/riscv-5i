# Makefile for the cocotb testbenches
#
# Usage:
#   make alu               # ALU testbench
#   make hazard            # HazardUnit testbench
#   make pipeline          # Whole-pipeline hazard / forwarding coverage
#   make compliance ARCH_TEST=<riscv-arch-test 3.9.1 checkout>
#   make ref               # pytest checks for the encoder and reference ISS
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

# The pipeline benches read internal CPU signals, so Verilator has to keep them
ifeq ($(SIM),verilator)
    EXTRA_ARGS += --public-flat-rw
endif

ifeq ($(BENCH),hazard)
    TOPLEVEL = HazardUnit
    COCOTB_TEST_MODULES = test_hazard_unit
    VERILOG_SOURCES = $(RTL_DIR)/riscv_pkg.sv $(RTL_DIR)/hazard_unit.sv
else ifeq ($(BENCH),pipeline)
    TOPLEVEL = CpuTbTop
    COCOTB_TEST_MODULES = test_pipeline_coverage
    VERILOG_SOURCES = $(RTL_DIR)/riscv_pkg.sv $(filter-out $(RTL_DIR)/riscv_pkg.sv $(RTL_DIR)/pynq_z2_top.sv,$(wildcard $(RTL_DIR)/*.sv)) cpu_tb_top.sv
else ifeq ($(BENCH),compliance)
    TOPLEVEL = CpuTbTop
    COCOTB_TEST_MODULES = test_compliance
    VERILOG_SOURCES = $(RTL_DIR)/riscv_pkg.sv $(filter-out $(RTL_DIR)/riscv_pkg.sv $(RTL_DIR)/pynq_z2_top.sv,$(wildcard $(RTL_DIR)/*.sv)) cpu_tb_top.sv
else
    TOPLEVEL = ALU
    COCOTB_TEST_MODULES = test_alu
    VERILOG_SOURCES = $(RTL_DIR)/riscv_pkg.sv $(RTL_DIR)/alu.sv
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: alu hazard pipeline compliance ref coverage

alu:
	$(MAKE) BENCH=alu SIM_BUILD=sim_build_alu COCOTB_RESULTS_FILE=results_alu.xml

hazard:
	$(MAKE) BENCH=hazard SIM_BUILD=sim_build_hazard COCOTB_RESULTS_FILE=results_hazard.xml

pipeline:
	$(MAKE) BENCH=pipeline SIM_BUILD=sim_build_pipeline COCOTB_RESULTS_FILE=results_pipeline.xml

# Builds the arch-test images with the reference ISS, then runs them on the RTL
compliance:
	@test -n "$(ARCH_TEST)" || { echo "Set ARCH_TEST=<riscv-arch-test 3.9.1 checkout>"; exit 1; }
	python3 build_compliance.py --suite $(ARCH_TEST)
	$(MAKE) BENCH=compliance SIM_BUILD=sim_build_compliance COCOTB_RESULTS_FILE=results_compliance.xml

ref:
	python3 -m pytest -q test_ref_model.py test_build_compliance.py

coverage:
	@mkdir -p coverage
	@for bench in alu hazard pipeline; do \
		if [ -f coverage_$$bench.dat ]; then \
			echo "[*] Line coverage for $$bench:"; \
			verilator_coverage --annotate coverage/$$bench --annotate-all coverage_$$bench.dat | tail -1; \
		else \
			echo "[!] WARNING: No coverage_$$bench.dat, run 'make $$bench' first."; \
		fi; \
	done
