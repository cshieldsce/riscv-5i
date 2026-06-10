// 5-Stage Pipelined RISC-V CPU Top-Level
import riscv_pkg::*;

/**
 * @brief 5-Stage Pipelined RISC-V CPU Top-Level Module
 * @details Implements a standard 5-stage pipeline:
 *          1. IF (Instruction Fetch): Fetches instruction from memory
 *          2. ID (Instruction Decode): Decodes instruction, reads registers, resolves hazards
 *          3. EX (Execute): ALU operations, branch resolution, address calculation
 *          4. MEM (Memory): Data memory access (Load/Store)
 *          5. WB (Writeback): Writes results back to register file
 * 
 *          Features:
 *          - Full forwarding (EX-to-EX, MEM-to-EX, WB-to-MEM)
 *          - Hazard detection (Load-Use stalls, Control hazards/flushes)
 *          - Memory-Mapped I/O support via Data Memory interface
 * 
 * @param clk        System Clock
 * @param rst        System Reset (Active High)
 * @param imem_addr  Instruction Memory Address
 * @param imem_data  Instruction Memory Data Input
 * @param imem_en    Instruction Memory Enable
 * @param dmem_addr  Data Memory Address
 * @param dmem_rdata Data Memory Read Data Input
 * @param dmem_wdata Data Memory Write Data Output
 * @param dmem_we    Data Memory Write Enable
 * @param dmem_be    Data Memory Byte Enable
 * @param dmem_funct3 Data Memory Access Type
 */
module PipelinedCPU (
    input  logic             clk,
    input  logic             rst,
    output logic [ALEN-1:0]  imem_addr,
    input  logic [31:0]      imem_data,
    output logic             imem_en,
    output logic [ALEN-1:0]  dmem_addr,
    input  logic [XLEN-1:0]  dmem_rdata,
    output logic [XLEN-1:0]  dmem_wdata,
    output logic             dmem_we,
    output logic [3:0]       dmem_be,
    output logic [2:0]       dmem_funct3
);
    // ------------------------------------------- //
    // -------- Pipeline Register Widths --------- //
    // ------------------------------------------- //

    // IF/ID: PC(XLEN) + Inst(32) + PC+4(XLEN)
    localparam IF_ID_WIDTH   = XLEN + 32 + XLEN;

    // ID/EX: 
    // Data: PC(X), PC+4(X), RD1(X), RD2(X), Imm(X), rs1(5), rs2(5), rd(5), funct3(3)
    // Control: RegWrite(1), MemWrite(1), ALUControl(4), ALUSrc(1), ALUSrcA(2), MemToReg(2), Branch(1), Jump(1), Jalr(1)
    localparam ID_EX_WIDTH   = (5 * XLEN) + 18 + 14;

    // EX/MEM:
    // Data: ALUResult(X), WriteData(X), rd(5), PC+4(X), funct3(3), rs2(5)
    // Control: RegWrite(1), MemWrite(1), MemToReg(2)
    localparam EX_MEM_WIDTH  = (3 * XLEN) + 13 + 4;

    // MEM/WB:
    // Data: ReadData(X), ALUResult(X), rd(5), PC+4(X)
    // Control: RegWrite(1), MemToReg(2)
    localparam MEM_WB_WIDTH  = (3 * XLEN) + 5 + 3;

    // ------------------------------------------- //
    // ----------- CPU Internal Signals ---------- //
    // ------------------------------------------- //

    // --- IF Stage Signals ---
    logic [XLEN-1:0] if_pc, if_instruction_wire, if_pc_plus_4;
    logic [31:0]     if_instruction; 
    logic [XLEN-1:0] next_pc; 

    // IF/ID Register
    logic [XLEN-1:0] if_id_pc, if_id_pc_plus_4;
    logic [31:0]     if_id_instruction;
    logic            if_id_valid;

    // --- ID Stage Signals ---
    logic [XLEN-1:0] id_read_data1, id_read_data2, id_imm_out;
    logic [4:0]      id_rs1, id_rs2, id_rd;
    opcode_t         id_opcode;
    logic [2:0]      id_funct3;
    logic [6:0]      id_funct7;

    // Control Signals
    logic            id_reg_write, id_mem_write;
    alu_op_t         id_alu_control;
    logic [1:0]      id_op_a_sel;
    logic            id_op_b_sel;
    logic [1:0]      id_wb_mux_sel;
    logic            id_branch, id_jump, id_jalr;

    // ID/EX Register Signals
    logic [XLEN-1:0] id_ex_pc, id_ex_pc_plus_4;
    logic [XLEN-1:0] id_ex_read_data1, id_ex_read_data2, id_ex_imm;
    logic [4:0]      id_ex_rs1, id_ex_rs2, id_ex_rd;
    logic [2:0]      id_ex_funct3;

    // ID/EX Control
    logic            id_ex_reg_write, id_ex_mem_write;
    alu_op_t         id_ex_alu_control;
    logic [1:0]      id_ex_op_a_sel;
    logic            id_ex_op_b_sel;
    logic [1:0]      id_ex_wb_mux_sel;
    logic            id_ex_branch, id_ex_jump, id_ex_jalr;

    // --- EX Stage Signals ---
    logic [XLEN-1:0] ex_alu_result, ex_alu_b_input; 
    logic            ex_zero;
    logic [XLEN-1:0] ex_branch_target;
    logic            branch_taken;

    // EX/MEM Register Signals
    logic [XLEN-1:0] ex_mem_alu_result, ex_mem_write_data; 
    logic [4:0]      ex_mem_rd;
    logic [4:0]      ex_mem_rs2;        
    logic [XLEN-1:0] ex_mem_pc_plus_4;
    logic [2:0]      ex_mem_funct3; 

    // EX/MEM Control
    logic            ex_mem_reg_write, ex_mem_mem_write;
    logic [1:0]      ex_mem_wb_mux_sel;

    // --- MEM Stage Signals ---
    logic [XLEN-1:0] mem_read_data;

    // MEM/WB Register Signals
    logic [XLEN-1:0] mem_wb_read_data, mem_wb_alu_result;
    logic [4:0]      mem_wb_rd;
    logic [XLEN-1:0] mem_wb_pc_plus_4;

    // MEM/WB Control
    logic            mem_wb_reg_write;
    logic [1:0]      mem_wb_wb_mux_sel;

    // --- WB Stage Signals ---
    logic [XLEN-1:0] wb_write_data; 

    // --- Hazard & Forwarding Signals ---
    logic [1:0]      forward_a, forward_b; 
    logic            stall_if, stall_id, flush_ex, flush_id;
    logic            branch_taken_ex; 

    assign branch_taken_ex = branch_taken | id_ex_jalr;

    // -------------------------------------------------- //
    // ----------- IF: Instruction Fetch Stage ---------- //
    // -------------------------------------------------- //   

    // Calculate JAL target early (in ID stage)
    logic [XLEN-1:0] jump_target_id; 
    assign jump_target_id = if_id_pc + id_imm_out;

    // JALR target masking (LSB must be 0)
    logic [XLEN-1:0] jalr_masked_pc;
    assign jalr_masked_pc = ex_alu_result & {{(XLEN-1){1'b1}}, 1'b0};

    IF_Stage if_stage_inst (
        .clk(clk),
        .rst(rst),
        .stall(stall_if),
        .branch_taken(branch_taken),
        .jalr_taken(id_ex_jalr),
        .jal_taken(id_jump),
        .branch_target(ex_branch_target),
        .jalr_target(jalr_masked_pc),
        .jal_target(jump_target_id),
        .instruction_in(imem_data),
        .pc_out(if_pc),
        .pc_plus_4(if_pc_plus_4),
        .instruction_out(if_instruction_wire)
    );
    
    assign if_instruction = if_instruction_wire[31:0];
    assign imem_addr = if_pc;
    assign imem_en = ~stall_id;

    // --- IF/ID Pipeline Register ---
    PipelineRegister #(IF_ID_WIDTH) if_id_reg (
        .clk(clk),
        .rst(rst),
        .en(~stall_id),
        .clear(flush_id),
        .in({if_pc, if_instruction, if_pc_plus_4}),
        .out({if_id_pc, if_id_instruction, if_id_pc_plus_4})
    );
    
    assign if_id_valid = (if_id_instruction != NOP_A);

    // --------------------------------------------------- //
    // ----------- ID: Instruction Decode Stage ---------- //
    // --------------------------------------------------- //

    logic [31:0] id_instruction_muxed;
    assign id_instruction_muxed = if_id_instruction;

    ID_Stage id_stage_inst (
        .clk(clk),
        .rst(rst),
        .instruction(id_instruction_muxed),
        .pc(if_id_pc),
        .reg_write_wb(mem_wb_reg_write),
        .write_data_wb(wb_write_data),
        .rd_wb(mem_wb_rd),
        .read_data1(id_read_data1),
        .read_data2(id_read_data2),
        .imm_out(id_imm_out),
        .rs1(id_rs1),
        .rs2(id_rs2),
        .rd(id_rd),
        .opcode(id_opcode),
        .funct3(id_funct3),
        .funct7(id_funct7),
        .reg_write(id_reg_write),
        .mem_write(id_mem_write),
        .alu_control(id_alu_control),
        .op_a_sel(id_op_a_sel),
        .op_b_sel(id_op_b_sel),
        .wb_mux_sel(id_wb_mux_sel),
        .branch(id_branch),
        .jump(id_jump),
        .jalr(id_jalr)
    );

    HazardUnit hazard_unit_inst (
        .id_rs1(id_rs1),
        .id_rs2(id_rs2),
        .id_branch(id_branch),
        .id_ex_rd(id_ex_rd),
        .id_ex_mem_read(id_ex_wb_mux_sel[0]), 
        .branch_taken_ex(branch_taken_ex),
        .jump_id_stage(id_jump),
        .stall_if(stall_if),
        .stall_id(stall_id),
        .flush_ex(flush_ex),
        .flush_id(flush_id)
    );

    // --- ID/EX Pipeline Register ---
    PipelineRegister #(ID_EX_WIDTH) id_ex_reg (
        .clk(clk),
        .rst(rst),
        .en(1'b1),        
        .clear(flush_ex), 
        .in({
            // Data Payload
            if_id_pc, if_id_pc_plus_4,
            id_read_data1, id_read_data2, id_imm_out, 
            id_rs1, id_rs2, id_rd, id_funct3,
            // Control Payload
            id_reg_write, id_mem_write,
            id_alu_control, id_op_a_sel, id_op_b_sel, id_wb_mux_sel, 
            id_branch, id_jump, id_jalr
        }),
        .out({
            // Data Payload
            id_ex_pc, id_ex_pc_plus_4, 
            id_ex_read_data1, id_ex_read_data2, id_ex_imm, 
            id_ex_rs1, id_ex_rs2, id_ex_rd, id_ex_funct3,
            // Control Payload
            id_ex_reg_write, id_ex_mem_write,
            id_ex_alu_control, id_ex_op_a_sel, id_ex_op_b_sel, id_ex_wb_mux_sel, 
            id_ex_branch, id_ex_jump, id_ex_jalr
        })
    );

    // -------------------------------------------------- //
    // ---------------- EX: Execute Stage --------------- //
    // -------------------------------------------------- //

    ForwardingUnit forwarding_unit_inst (
        .id_ex_rs1(id_ex_rs1),
        .id_ex_rs2(id_ex_rs2),
        .ex_mem_rd(ex_mem_rd),
        .ex_mem_reg_write(ex_mem_reg_write),
        .mem_wb_rd(mem_wb_rd),
        .mem_wb_reg_write(mem_wb_reg_write),
        .forward_a(forward_a),
        .forward_b(forward_b)
    );

    EX_Stage ex_stage_inst (
        .pc(id_ex_pc),
        .imm(id_ex_imm),
        .rs1_data(id_ex_read_data1),
        .rs2_data(id_ex_read_data2),
        .forward_a(forward_a),
        .forward_b(forward_b),
        .ex_mem_alu_result(ex_mem_alu_result),
        .wb_write_data(wb_write_data),
        .alu_control(id_ex_alu_control),
        .op_a_sel(id_ex_op_a_sel),
        .op_b_sel(id_ex_op_b_sel),
        .branch_en(id_ex_branch),
        .funct3(id_ex_funct3),
        .alu_result(ex_alu_result),
        .alu_zero(ex_zero),
        .branch_taken(branch_taken),
        .branch_target(ex_branch_target),
        .rs2_data_forwarded(ex_alu_b_input) 
    );

    // --- EX/MEM Pipeline Register ---
    PipelineRegister #(EX_MEM_WIDTH) ex_mem_reg (
        .clk(clk),
        .rst(rst),
        .en(1'b1),    
        .clear(1'b0), 
        .in({
            // Data Payload
            ex_alu_result,      
            ex_alu_b_input,           
            id_ex_rd,           
            id_ex_pc_plus_4,    
            id_ex_funct3,
            id_ex_rs2,
            // Control Payload
            id_ex_reg_write, id_ex_mem_write, id_ex_wb_mux_sel
        }),
        .out({
            // Data Payload
            ex_mem_alu_result, ex_mem_write_data, ex_mem_rd, ex_mem_pc_plus_4, ex_mem_funct3,
            ex_mem_rs2,         
            // Control Payload
            ex_mem_reg_write, ex_mem_mem_write, ex_mem_wb_mux_sel
        })
    );

    // -------------------------------------------------- //
    // -------------- MEM: Memory Stage ----------------- //
    // -------------------------------------------------- //

    MEM_Stage mem_stage_inst (
        .clk(clk),
        .rst(rst),
        .ex_mem_mem_write(ex_mem_mem_write),
        .ex_mem_alu_result(ex_mem_alu_result),
        .ex_mem_write_data(ex_mem_write_data),
        .ex_mem_funct3(ex_mem_funct3),
        .ex_mem_rs2(ex_mem_rs2),
        .wb_reg_write(mem_wb_reg_write),
        .wb_rd(mem_wb_rd),
        .wb_write_data(wb_write_data),
        .dmem_addr(dmem_addr),
        .dmem_wdata(dmem_wdata),
        .dmem_we(dmem_we),
        .dmem_be(dmem_be),
        .dmem_funct3(dmem_funct3)
    );
    
    assign mem_read_data = dmem_rdata;
    
    // --- MEM/WB Pipeline Register ---
    PipelineRegister #(MEM_WB_WIDTH) mem_wb_reg (
        .clk(clk),
        .rst(rst),
        .en(1'b1),    
        .clear(1'b0), 
        .in({
            // Data Payload
            mem_read_data,      
            ex_mem_alu_result,  
            ex_mem_rd,          
            ex_mem_pc_plus_4,   
            // Control Payload
            ex_mem_reg_write, ex_mem_wb_mux_sel
        }),
        .out({
            // Data Payload
            mem_wb_read_data, mem_wb_alu_result, mem_wb_rd, mem_wb_pc_plus_4,
            // Control Payload
            mem_wb_reg_write, mem_wb_wb_mux_sel
        })
    );

    // --------------------------------------------------- //
    // ------------- WB: Writeback Stage ----------------- //
    // --------------------------------------------------- //

    WB_Stage wb_stage_inst (
        .mem_wb_wb_mux_sel(mem_wb_wb_mux_sel),
        .mem_wb_alu_result(mem_wb_alu_result),
        .mem_wb_pc_plus_4(mem_wb_pc_plus_4),
        .dmem_read_data(mem_read_data),
        .wb_write_data(wb_write_data)
    );

endmodule
