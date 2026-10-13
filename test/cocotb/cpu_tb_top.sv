import riscv_pkg::*;

/**
 * @brief cocotb wrapper: PipelinedCPU plus the real instruction and data memories
 * @details Same wiring as test/tb/pipelined_cpu_tb.sv, without the $readmemh and
 *          the fixed timeout, so cocotb can load a program and decide when to stop.
 *          Nothing under src/ is changed. The pipeline signals the coverage test
 *          samples are read through the hierarchy (cpu.*).
 */
module CpuTbTop (
    input  logic clk,
    input  logic rst,
    output logic [LED_WIDTH-1:0] leds_out
);
    logic [ALEN-1:0] imem_addr;
    logic [XLEN-1:0] imem_data;
    logic            imem_en;
    logic [ALEN-1:0] dmem_addr;
    logic [XLEN-1:0] dmem_rdata, dmem_wdata;
    logic            dmem_we;
    logic [3:0]      dmem_be;
    logic [2:0]      dmem_funct3;

    PipelinedCPU cpu (
        .clk(clk),
        .rst(rst),
        .imem_addr(imem_addr),
        .imem_data(imem_data),
        .imem_en(imem_en),
        .dmem_addr(dmem_addr),
        .dmem_rdata(dmem_rdata),
        .dmem_wdata(dmem_wdata),
        .dmem_we(dmem_we),
        .dmem_be(dmem_be),
        .dmem_funct3(dmem_funct3)
    );

    InstructionMemory imem (
        .clk(clk),
        .rst(rst),
        .en(imem_en),
        .Address(imem_addr),
        .Instruction(imem_data)
    );

    // Fill both memories so unwritten words read as NOP / 0 instead of X. cocotb
    // then loads the program over the top.
    initial begin
        for (int i = 0; i <= RAM_MEMORY_SIZE; i++) imem.rom_memory[i] = NOP_A;
        for (int i = 0; i < RAM_MEMORY_SIZE; i++)  dmem.ram_memory[i] = '0;
    end

    DataMemory dmem (
        .clk(clk),
        .rst(rst),
        .MemWrite(dmem_we),
        .be(dmem_be),
        .funct3(dmem_funct3),
        .Address(dmem_addr),
        .WriteData(dmem_wdata),
        .ReadData(dmem_rdata),
        .leds_out(leds_out)
    );
endmodule
