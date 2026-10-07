module ALU (
	A,
	B,
	ALUControl,
	Result,
	Zero
);
	reg _sv2v_0;
	localparam riscv_pkg_XLEN = 32;
	input wire [31:0] A;
	input wire [31:0] B;
	input wire [3:0] ALUControl;
	output reg [31:0] Result;
	output wire Zero;
	wire [4:0] alu_shamt;
	assign alu_shamt = B[4:0];
	always @(*) begin : ALU_Operation
		if (_sv2v_0)
			;
		case (ALUControl)
			4'b0000: Result = A & B;
			4'b0001: Result = A | B;
			4'b1001: Result = A ^ B;
			4'b0010: Result = A + B;
			4'b0110: Result = A - B;
			4'b0111: Result = ($signed(A) < $signed(B) ? {{31 {1'b0}}, 1'b1} : {riscv_pkg_XLEN {1'b0}});
			4'b1000: Result = (A < B ? {{31 {1'b0}}, 1'b1} : {riscv_pkg_XLEN {1'b0}});
			4'b1010: Result = A << alu_shamt;
			4'b1011: Result = A >> alu_shamt;
			4'b1100: Result = $signed(A) >>> alu_shamt;
			default: Result = {riscv_pkg_XLEN {1'b0}};
		endcase
	end
	assign Zero = Result == {riscv_pkg_XLEN {1'b0}};
	initial _sv2v_0 = 0;
endmodule
module ControlUnit (
	opcode,
	funct3,
	funct7,
	reg_write,
	alu_control,
	op_a_sel,
	op_b_sel,
	mem_write,
	wb_mux_sel,
	branch,
	jump,
	jalr
);
	reg _sv2v_0;
	input wire [6:0] opcode;
	input wire [2:0] funct3;
	input wire [6:0] funct7;
	output reg reg_write;
	output reg [3:0] alu_control;
	output reg [1:0] op_a_sel;
	output reg op_b_sel;
	output reg mem_write;
	output reg [1:0] wb_mux_sel;
	output reg branch;
	output reg jump;
	output reg jalr;
	always @(*) begin : ControlLogic
		if (_sv2v_0)
			;
		reg_write = 1'b0;
		alu_control = 4'b0010;
		op_a_sel = 2'b00;
		op_b_sel = 1'b0;
		mem_write = 1'b0;
		wb_mux_sel = 2'b00;
		branch = 1'b0;
		jump = 1'b0;
		jalr = 1'b0;
		case (opcode)
			7'b0110011: begin : RegisterArithmetic
				reg_write = 1'b1;
				op_b_sel = 1'b0;
				wb_mux_sel = 2'b00;
				case (funct3)
					3'b000: alu_control = (funct7[5] ? 4'b0110 : 4'b0010);
					3'b001: alu_control = 4'b1010;
					3'b010: alu_control = 4'b0111;
					3'b011: alu_control = 4'b1000;
					3'b100: alu_control = 4'b1001;
					3'b101: alu_control = (funct7[5] ? 4'b1100 : 4'b1011);
					3'b110: alu_control = 4'b0001;
					3'b111: alu_control = 4'b0000;
					default: alu_control = 4'b0010;
				endcase
			end
			7'b0010011: begin : ImmediateArithmetic
				reg_write = 1'b1;
				op_b_sel = 1'b1;
				wb_mux_sel = 2'b00;
				case (funct3)
					3'b000: alu_control = 4'b0010;
					3'b001: alu_control = 4'b1010;
					3'b010: alu_control = 4'b0111;
					3'b011: alu_control = 4'b1000;
					3'b100: alu_control = 4'b1001;
					3'b101: alu_control = (funct7[5] ? 4'b1100 : 4'b1011);
					3'b110: alu_control = 4'b0001;
					3'b111: alu_control = 4'b0000;
					default: alu_control = 4'b0010;
				endcase
			end
			7'b0000011: begin : LoadFromMemory
				reg_write = 1'b1;
				op_b_sel = 1'b1;
				wb_mux_sel = 2'b01;
				alu_control = 4'b0010;
			end
			7'b0100011: begin : StoreToMemory
				op_b_sel = 1'b1;
				mem_write = 1'b1;
				alu_control = 4'b0010;
			end
			7'b1100011: begin : ConditionalBranches
				branch = 1'b1;
				op_b_sel = 1'b0;
				wb_mux_sel = 2'b00;
				case (funct3)
					3'b000, 3'b001: alu_control = 4'b0110;
					3'b100, 3'b101: alu_control = 4'b0111;
					3'b110, 3'b111: alu_control = 4'b1000;
					default: alu_control = 4'b0110;
				endcase
			end
			7'b1101111: begin : UnconditionalJump
				jump = 1'b1;
				reg_write = 1'b1;
				wb_mux_sel = 2'b10;
				alu_control = 4'b0010;
			end
			7'b1100111: begin : JumpAndLinkRegisters
				jalr = 1'b1;
				reg_write = 1'b1;
				op_b_sel = 1'b1;
				wb_mux_sel = 2'b10;
				alu_control = 4'b0010;
			end
			7'b0110111: begin : LoadUpperImmediate
				reg_write = 1'b1;
				op_b_sel = 1'b1;
				op_a_sel = 2'b10;
				wb_mux_sel = 2'b00;
				alu_control = 4'b0010;
			end
			7'b0010111: begin : AddUpperImmediateToPC
				reg_write = 1'b1;
				op_b_sel = 1'b1;
				op_a_sel = 2'b01;
				wb_mux_sel = 2'b00;
				alu_control = 4'b0010;
			end
			7'b1110011: begin : SystemInstructions
				
			end
			7'b0001111: begin : MemoryOrdering
				
			end
			default: begin : UnknownOpcode
				
			end
		endcase
	end
	initial _sv2v_0 = 0;
endmodule
module EX_Stage (
	pc,
	imm,
	rs1_data,
	rs2_data,
	forward_a,
	forward_b,
	ex_mem_alu_result,
	wb_write_data,
	alu_control,
	op_a_sel,
	op_b_sel,
	branch_en,
	funct3,
	alu_result,
	alu_zero,
	branch_taken,
	branch_target,
	rs2_data_forwarded
);
	reg _sv2v_0;
	localparam riscv_pkg_XLEN = 32;
	input wire [31:0] pc;
	input wire [31:0] imm;
	input wire [31:0] rs1_data;
	input wire [31:0] rs2_data;
	input wire [1:0] forward_a;
	input wire [1:0] forward_b;
	input wire [31:0] ex_mem_alu_result;
	input wire [31:0] wb_write_data;
	input wire [3:0] alu_control;
	input wire [1:0] op_a_sel;
	input wire op_b_sel;
	input wire branch_en;
	input wire [2:0] funct3;
	output wire [31:0] alu_result;
	output wire alu_zero;
	output reg branch_taken;
	output wire [31:0] branch_target;
	output reg [31:0] rs2_data_forwarded;
	reg [31:0] ex_alu_in_a_fwd;
	reg [31:0] ex_alu_in_a;
	wire [31:0] ex_alu_in_b;
	always @(*) begin : ForwardA_MUX
		if (_sv2v_0)
			;
		case (forward_a)
			2'b00: ex_alu_in_a_fwd = rs1_data;
			2'b01: ex_alu_in_a_fwd = wb_write_data;
			2'b10: ex_alu_in_a_fwd = ex_mem_alu_result;
			default: ex_alu_in_a_fwd = rs1_data;
		endcase
	end
	always @(*) begin : ForwardB_MUX
		if (_sv2v_0)
			;
		case (forward_b)
			2'b00: rs2_data_forwarded = rs2_data;
			2'b01: rs2_data_forwarded = wb_write_data;
			2'b10: rs2_data_forwarded = ex_mem_alu_result;
			default: rs2_data_forwarded = rs2_data;
		endcase
	end
	always @(*) begin : ALUInputA_MUX
		if (_sv2v_0)
			;
		case (op_a_sel)
			2'b00: ex_alu_in_a = ex_alu_in_a_fwd;
			2'b01: ex_alu_in_a = pc;
			2'b10: ex_alu_in_a = {riscv_pkg_XLEN {1'b0}};
			default: ex_alu_in_a = ex_alu_in_a_fwd;
		endcase
	end
	assign ex_alu_in_b = (op_b_sel ? imm : rs2_data_forwarded);
	ALU alu_inst(
		.A(ex_alu_in_a),
		.B(ex_alu_in_b),
		.ALUControl(alu_control),
		.Result(alu_result),
		.Zero(alu_zero)
	);
	always @(*) begin : BranchResolution
		if (_sv2v_0)
			;
		if (branch_en) begin : BranchEnabled
			case (funct3)
				3'b000: branch_taken = alu_zero;
				3'b001: branch_taken = ~alu_zero;
				3'b100: branch_taken = alu_result[0];
				3'b101: branch_taken = ~alu_result[0];
				3'b110: branch_taken = alu_result[0];
				3'b111: branch_taken = ~alu_result[0];
				default: branch_taken = 1'b0;
			endcase
		end
		else begin : BranchDisabled
			branch_taken = 1'b0;
		end
	end
	assign branch_target = pc + imm;
	initial _sv2v_0 = 0;
endmodule
module ForwardingUnit (
	id_ex_rs1,
	id_ex_rs2,
	ex_mem_rd,
	ex_mem_reg_write,
	mem_wb_rd,
	mem_wb_reg_write,
	forward_a,
	forward_b
);
	reg _sv2v_0;
	input wire [4:0] id_ex_rs1;
	input wire [4:0] id_ex_rs2;
	input wire [4:0] ex_mem_rd;
	input wire ex_mem_reg_write;
	input wire [4:0] mem_wb_rd;
	input wire mem_wb_reg_write;
	output reg [1:0] forward_a;
	output reg [1:0] forward_b;
	function automatic has_ex_hazard;
		input reg [4:0] rd;
		input reg [4:0] rs;
		input reg reg_write;
		has_ex_hazard = (reg_write && (rd != 5'b00000)) && (rd == rs);
	endfunction
	function automatic has_mem_hazard;
		input reg [4:0] mem_rd;
		input reg [4:0] ex_rd;
		input reg [4:0] rs;
		input reg mem_reg_write;
		input reg ex_reg_write;
		reg mem_match;
		reg ex_match;
		begin
			mem_match = (mem_reg_write && (mem_rd != 5'b00000)) && (mem_rd == rs);
			ex_match = has_ex_hazard(ex_rd, rs, ex_reg_write);
			has_mem_hazard = mem_match && !ex_match;
		end
	endfunction
	always @(*) begin : ForwardingLogic
		if (_sv2v_0)
			;
		forward_a = 2'b00;
		forward_b = 2'b00;
		if (has_ex_hazard(ex_mem_rd, id_ex_rs1, ex_mem_reg_write)) begin : EXHazardA
			forward_a = 2'b10;
		end
		if (has_ex_hazard(ex_mem_rd, id_ex_rs2, ex_mem_reg_write)) begin : EXHazardB
			forward_b = 2'b10;
		end
		if (has_mem_hazard(mem_wb_rd, ex_mem_rd, id_ex_rs1, mem_wb_reg_write, ex_mem_reg_write)) begin : MEMHazardA
			forward_a = 2'b01;
		end
		if (has_mem_hazard(mem_wb_rd, ex_mem_rd, id_ex_rs2, mem_wb_reg_write, ex_mem_reg_write)) begin : MEMHazardB
			forward_b = 2'b01;
		end
	end
	initial _sv2v_0 = 0;
endmodule
module HazardUnit (
	id_rs1,
	id_rs2,
	id_branch,
	id_ex_rd,
	id_ex_mem_read,
	branch_taken_ex,
	jump_id_stage,
	stall_if,
	stall_id,
	flush_ex,
	flush_id
);
	reg _sv2v_0;
	input wire [4:0] id_rs1;
	input wire [4:0] id_rs2;
	input wire id_branch;
	input wire [4:0] id_ex_rd;
	input wire id_ex_mem_read;
	input wire branch_taken_ex;
	input wire jump_id_stage;
	output reg stall_if;
	output reg stall_id;
	output reg flush_ex;
	output reg flush_id;
	function automatic has_register_dependency;
		input reg [4:0] rd;
		input reg [4:0] rs1;
		input reg [4:0] rs2;
		has_register_dependency = (rd != 5'b00000) && ((rd == rs1) || (rd == rs2));
	endfunction
	function automatic is_load_use_hazard;
		input reg ex_is_load;
		input reg [4:0] ex_rd;
		input reg [4:0] id_rs1;
		input reg [4:0] id_rs2;
		is_load_use_hazard = ex_is_load && has_register_dependency(ex_rd, id_rs1, id_rs2);
	endfunction
	function automatic is_alu_branch_hazard;
		input reg ex_is_load;
		input reg [4:0] ex_rd;
		input reg id_is_branch;
		input reg [4:0] id_rs1;
		input reg [4:0] id_rs2;
		is_alu_branch_hazard = (!ex_is_load && id_is_branch) && has_register_dependency(ex_rd, id_rs1, id_rs2);
	endfunction
	always @(*) begin : HazardDetection
		if (_sv2v_0)
			;
		stall_if = 1'b0;
		stall_id = 1'b0;
		flush_ex = 1'b0;
		flush_id = 1'b0;
		if (is_load_use_hazard(id_ex_mem_read, id_ex_rd, id_rs1, id_rs2)) begin : LoadUse_Flush
			stall_if = 1'b1;
			stall_id = 1'b1;
			flush_ex = 1'b1;
		end
		else if (is_alu_branch_hazard(id_ex_mem_read, id_ex_rd, id_branch, id_rs1, id_rs2)) begin : ALUBranch_Flush
			stall_if = 1'b1;
			stall_id = 1'b1;
			flush_ex = 1'b1;
		end
		else if (branch_taken_ex) begin : BranchJALR_Flush
			flush_id = 1'b1;
			flush_ex = 1'b1;
		end
		else if (jump_id_stage) begin : JAL_Flush
			flush_id = 1'b1;
		end
	end
	initial _sv2v_0 = 0;
endmodule
module ID_Stage (
	clk,
	rst,
	instruction,
	pc,
	reg_write_wb,
	write_data_wb,
	rd_wb,
	read_data1,
	read_data2,
	imm_out,
	rs1,
	rs2,
	rd,
	opcode,
	funct3,
	funct7,
	reg_write,
	mem_write,
	alu_control,
	op_a_sel,
	op_b_sel,
	wb_mux_sel,
	branch,
	jump,
	jalr
);
	input wire clk;
	input wire rst;
	input wire [31:0] instruction;
	localparam riscv_pkg_XLEN = 32;
	input wire [31:0] pc;
	input wire reg_write_wb;
	input wire [31:0] write_data_wb;
	input wire [4:0] rd_wb;
	output wire [31:0] read_data1;
	output wire [31:0] read_data2;
	output wire [31:0] imm_out;
	output wire [4:0] rs1;
	output wire [4:0] rs2;
	output wire [4:0] rd;
	output wire [6:0] opcode;
	output wire [2:0] funct3;
	output wire [6:0] funct7;
	output wire reg_write;
	output wire mem_write;
	output wire [3:0] alu_control;
	output wire [1:0] op_a_sel;
	output wire op_b_sel;
	output wire [1:0] wb_mux_sel;
	output wire branch;
	output wire jump;
	output wire jalr;
	assign opcode = instruction[6:0];
	assign rd = instruction[11:7];
	assign funct3 = instruction[14:12];
	assign rs1 = instruction[19:15];
	assign rs2 = instruction[24:20];
	assign funct7 = instruction[31:25];
	ControlUnit control_unit_inst(
		.opcode(opcode),
		.funct3(funct3),
		.funct7(funct7),
		.reg_write(reg_write),
		.alu_control(alu_control),
		.op_a_sel(op_a_sel),
		.op_b_sel(op_b_sel),
		.mem_write(mem_write),
		.wb_mux_sel(wb_mux_sel),
		.branch(branch),
		.jump(jump),
		.jalr(jalr)
	);
	RegFile reg_file_inst(
		.clk(clk),
		.rst(rst),
		.RegWrite(reg_write_wb),
		.rs1(rs1),
		.rs2(rs2),
		.rd(rd_wb),
		.write_data(write_data_wb),
		.read_data1(read_data1),
		.read_data2(read_data2)
	);
	ImmGen imm_gen_inst(
		.instruction(instruction),
		.opcode(opcode),
		.imm_out(imm_out)
	);
endmodule
module IF_Stage (
	clk,
	rst,
	stall,
	branch_taken,
	jalr_taken,
	jal_taken,
	branch_target,
	jalr_target,
	jal_target,
	instruction_in,
	pc_out,
	pc_plus_4,
	instruction_out
);
	reg _sv2v_0;
	input wire clk;
	input wire rst;
	input wire stall;
	input wire branch_taken;
	input wire jalr_taken;
	input wire jal_taken;
	localparam riscv_pkg_XLEN = 32;
	input wire [31:0] branch_target;
	input wire [31:0] jalr_target;
	input wire [31:0] jal_target;
	input wire [31:0] instruction_in;
	output wire [31:0] pc_out;
	output wire [31:0] pc_plus_4;
	output wire [31:0] instruction_out;
	reg [31:0] if_pc_reg;
	reg [31:0] if_next_pc;
	wire [31:0] if_pc_plus_4_calc;
	assign if_pc_plus_4_calc = if_pc_reg + 4;
	always @(*) begin : SelectNextPC
		if (_sv2v_0)
			;
		if (stall) begin : Stalled
			if_next_pc = if_pc_reg;
		end
		else if (jalr_taken) begin : JALRTaken
			if_next_pc = jalr_target;
		end
		else if (branch_taken) begin : BranchTaken
			if_next_pc = branch_target;
		end
		else if (jal_taken) begin : JALTaken
			if_next_pc = jal_target;
		end
		else begin : IncrementPC
			if_next_pc = if_pc_plus_4_calc;
		end
	end
	always @(posedge clk) begin : PC_Register
		if (rst) begin : ResetPC
			if_pc_reg <= {riscv_pkg_XLEN {1'b0}};
		end
		else begin : UpdatePC
			if_pc_reg <= if_next_pc;
		end
	end
	assign pc_out = if_pc_reg;
	assign pc_plus_4 = if_pc_plus_4_calc;
	assign instruction_out = instruction_in;
	initial _sv2v_0 = 0;
endmodule
module ImmGen (
	instruction,
	opcode,
	imm_out
);
	reg _sv2v_0;
	localparam riscv_pkg_XLEN = 32;
	input wire [31:0] instruction;
	input wire [6:0] opcode;
	output reg [31:0] imm_out;
	function automatic [31:0] extract_imm_i;
		input reg [31:0] inst;
		extract_imm_i = {{20 {inst[31]}}, inst[31:20]};
	endfunction
	function automatic [31:0] extract_imm_s;
		input reg [31:0] inst;
		extract_imm_s = {{20 {inst[31]}}, inst[31:25], inst[11:7]};
	endfunction
	function automatic [31:0] extract_imm_b;
		input reg [31:0] inst;
		extract_imm_b = {{19 {inst[31]}}, inst[31], inst[7], inst[30:25], inst[11:8], 1'b0};
	endfunction
	function automatic [31:0] extract_imm_j;
		input reg [31:0] inst;
		extract_imm_j = {{11 {inst[31]}}, inst[31], inst[19:12], inst[20], inst[30:21], 1'b0};
	endfunction
	function automatic [31:0] extract_imm_u;
		input reg [31:0] inst;
		extract_imm_u = {inst[31:12], 12'b000000000000};
	endfunction
	always @(*) begin : ImmSelection
		if (_sv2v_0)
			;
		case (opcode)
			7'b0010011, 7'b0000011, 7'b1100111: imm_out = extract_imm_i(instruction);
			7'b0100011: imm_out = extract_imm_s(instruction);
			7'b1100011: imm_out = extract_imm_b(instruction);
			7'b1101111: imm_out = extract_imm_j(instruction);
			7'b0110111, 7'b0010111: imm_out = extract_imm_u(instruction);
			default: imm_out = {riscv_pkg_XLEN {1'b0}};
		endcase
	end
	initial _sv2v_0 = 0;
endmodule
module MEM_Stage (
	clk,
	rst,
	ex_mem_mem_write,
	ex_mem_alu_result,
	ex_mem_write_data,
	ex_mem_funct3,
	ex_mem_rs2,
	wb_reg_write,
	wb_rd,
	wb_write_data,
	dmem_addr,
	dmem_wdata,
	dmem_we,
	dmem_be,
	dmem_funct3
);
	input wire clk;
	input wire rst;
	input wire ex_mem_mem_write;
	localparam riscv_pkg_XLEN = 32;
	input wire [31:0] ex_mem_alu_result;
	input wire [31:0] ex_mem_write_data;
	input wire [2:0] ex_mem_funct3;
	input wire [4:0] ex_mem_rs2;
	input wire wb_reg_write;
	input wire [4:0] wb_rd;
	input wire [31:0] wb_write_data;
	localparam riscv_pkg_ALEN = 32;
	output wire [31:0] dmem_addr;
	output wire [31:0] dmem_wdata;
	output wire dmem_we;
	output wire [3:0] dmem_be;
	output wire [2:0] dmem_funct3;
	function automatic [3:0] get_byte_enable;
		input reg [2:0] funct3;
		input reg [1:0] addr_lsb;
		case (funct3)
			3'b000: begin : ByteEnable
				case (addr_lsb)
					2'b00: get_byte_enable = 4'b0001;
					2'b01: get_byte_enable = 4'b0010;
					2'b10: get_byte_enable = 4'b0100;
					2'b11: get_byte_enable = 4'b1000;
				endcase
			end
			3'b001: begin : HalfwordEnable
				case (addr_lsb[1])
					1'b0: get_byte_enable = 4'b0011;
					1'b1: get_byte_enable = 4'b1100;
				endcase
			end
			default: get_byte_enable = 4'b1111;
		endcase
	endfunction
	function automatic should_forward_store_data;
		input reg wb_reg_write;
		input reg [4:0] wb_rd;
		input reg [4:0] mem_rs2;
		should_forward_store_data = (wb_reg_write && (wb_rd != 5'b00000)) && (wb_rd == mem_rs2);
	endfunction
	function automatic [31:0] get_store_data;
		input reg wb_reg_write;
		input reg [4:0] wb_rd;
		input reg [4:0] mem_rs2;
		input reg [31:0] wb_data;
		input reg [31:0] mem_data;
		if (should_forward_store_data(wb_reg_write, wb_rd, mem_rs2)) begin : ForwardStoreData
			get_store_data = wb_data;
		end
		else begin : NoForwardStoreData
			get_store_data = mem_data;
		end
	endfunction
	wire [31:0] mem_store_data_fwd;
	assign mem_store_data_fwd = get_store_data(wb_reg_write, wb_rd, ex_mem_rs2, wb_write_data, ex_mem_write_data);
	assign dmem_addr = ex_mem_alu_result;
	assign dmem_wdata = mem_store_data_fwd;
	assign dmem_we = ex_mem_mem_write;
	assign dmem_funct3 = ex_mem_funct3;
	assign dmem_be = get_byte_enable(ex_mem_funct3, ex_mem_alu_result[1:0]);
endmodule
module PipelinedCPU (
	clk,
	rst,
	imem_addr,
	imem_data,
	imem_en,
	dmem_addr,
	dmem_rdata,
	dmem_wdata,
	dmem_we,
	dmem_be,
	dmem_funct3
);
	input wire clk;
	input wire rst;
	localparam riscv_pkg_ALEN = 32;
	output wire [31:0] imem_addr;
	input wire [31:0] imem_data;
	output wire imem_en;
	output wire [31:0] dmem_addr;
	localparam riscv_pkg_XLEN = 32;
	input wire [31:0] dmem_rdata;
	output wire [31:0] dmem_wdata;
	output wire dmem_we;
	output wire [3:0] dmem_be;
	output wire [2:0] dmem_funct3;
	localparam IF_ID_WIDTH = 96;
	localparam ID_EX_WIDTH = 192;
	localparam EX_MEM_WIDTH = 113;
	localparam MEM_WB_WIDTH = 104;
	wire [31:0] if_pc;
	wire [31:0] if_instruction_wire;
	wire [31:0] if_pc_plus_4;
	wire [31:0] if_instruction;
	wire [31:0] next_pc;
	wire [31:0] if_id_pc;
	wire [31:0] if_id_pc_plus_4;
	wire [31:0] if_id_instruction;
	wire if_id_valid;
	wire [31:0] id_read_data1;
	wire [31:0] id_read_data2;
	wire [31:0] id_imm_out;
	wire [4:0] id_rs1;
	wire [4:0] id_rs2;
	wire [4:0] id_rd;
	wire [6:0] id_opcode;
	wire [2:0] id_funct3;
	wire [6:0] id_funct7;
	wire id_reg_write;
	wire id_mem_write;
	wire [3:0] id_alu_control;
	wire [1:0] id_op_a_sel;
	wire id_op_b_sel;
	wire [1:0] id_wb_mux_sel;
	wire id_branch;
	wire id_jump;
	wire id_jalr;
	wire [31:0] id_ex_pc;
	wire [31:0] id_ex_pc_plus_4;
	wire [31:0] id_ex_read_data1;
	wire [31:0] id_ex_read_data2;
	wire [31:0] id_ex_imm;
	wire [4:0] id_ex_rs1;
	wire [4:0] id_ex_rs2;
	wire [4:0] id_ex_rd;
	wire [2:0] id_ex_funct3;
	wire id_ex_reg_write;
	wire id_ex_mem_write;
	wire [3:0] id_ex_alu_control;
	wire [1:0] id_ex_op_a_sel;
	wire id_ex_op_b_sel;
	wire [1:0] id_ex_wb_mux_sel;
	wire id_ex_branch;
	wire id_ex_jump;
	wire id_ex_jalr;
	wire [31:0] ex_alu_result;
	wire [31:0] ex_alu_b_input;
	wire ex_zero;
	wire [31:0] ex_branch_target;
	wire branch_taken;
	wire [31:0] ex_mem_alu_result;
	wire [31:0] ex_mem_write_data;
	wire [4:0] ex_mem_rd;
	wire [4:0] ex_mem_rs2;
	wire [31:0] ex_mem_pc_plus_4;
	wire [2:0] ex_mem_funct3;
	wire ex_mem_reg_write;
	wire ex_mem_mem_write;
	wire [1:0] ex_mem_wb_mux_sel;
	wire [31:0] mem_read_data;
	wire [31:0] mem_wb_read_data;
	wire [31:0] mem_wb_alu_result;
	wire [4:0] mem_wb_rd;
	wire [31:0] mem_wb_pc_plus_4;
	wire mem_wb_reg_write;
	wire [1:0] mem_wb_wb_mux_sel;
	wire [31:0] wb_write_data;
	wire [1:0] forward_a;
	wire [1:0] forward_b;
	wire stall_if;
	wire stall_id;
	wire flush_ex;
	wire flush_id;
	wire branch_taken_ex;
	assign branch_taken_ex = branch_taken | id_ex_jalr;
	wire [31:0] jump_target_id;
	assign jump_target_id = if_id_pc + id_imm_out;
	wire [31:0] jalr_masked_pc;
	assign jalr_masked_pc = ex_alu_result & {{31 {1'b1}}, 1'b0};
	IF_Stage if_stage_inst(
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
	PipelineRegister #(.WIDTH(IF_ID_WIDTH)) if_id_reg(
		.clk(clk),
		.rst(rst),
		.en(~stall_id),
		.clear(flush_id),
		.in({if_pc, if_instruction, if_pc_plus_4}),
		.out({if_id_pc, if_id_instruction, if_id_pc_plus_4})
	);
	localparam [31:0] riscv_pkg_NOP_A = 32'h00000013;
	assign if_id_valid = if_id_instruction != riscv_pkg_NOP_A;
	wire [31:0] id_instruction_muxed;
	assign id_instruction_muxed = if_id_instruction;
	ID_Stage id_stage_inst(
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
	HazardUnit hazard_unit_inst(
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
	PipelineRegister #(.WIDTH(ID_EX_WIDTH)) id_ex_reg(
		.clk(clk),
		.rst(rst),
		.en(1'b1),
		.clear(flush_ex),
		.in({if_id_pc, if_id_pc_plus_4, id_read_data1, id_read_data2, id_imm_out, id_rs1, id_rs2, id_rd, id_funct3, id_reg_write, id_mem_write, id_alu_control, id_op_a_sel, id_op_b_sel, id_wb_mux_sel, id_branch, id_jump, id_jalr}),
		.out({id_ex_pc, id_ex_pc_plus_4, id_ex_read_data1, id_ex_read_data2, id_ex_imm, id_ex_rs1, id_ex_rs2, id_ex_rd, id_ex_funct3, id_ex_reg_write, id_ex_mem_write, id_ex_alu_control, id_ex_op_a_sel, id_ex_op_b_sel, id_ex_wb_mux_sel, id_ex_branch, id_ex_jump, id_ex_jalr})
	);
	ForwardingUnit forwarding_unit_inst(
		.id_ex_rs1(id_ex_rs1),
		.id_ex_rs2(id_ex_rs2),
		.ex_mem_rd(ex_mem_rd),
		.ex_mem_reg_write(ex_mem_reg_write),
		.mem_wb_rd(mem_wb_rd),
		.mem_wb_reg_write(mem_wb_reg_write),
		.forward_a(forward_a),
		.forward_b(forward_b)
	);
	EX_Stage ex_stage_inst(
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
	PipelineRegister #(.WIDTH(EX_MEM_WIDTH)) ex_mem_reg(
		.clk(clk),
		.rst(rst),
		.en(1'b1),
		.clear(1'b0),
		.in({ex_alu_result, ex_alu_b_input, id_ex_rd, id_ex_pc_plus_4, id_ex_funct3, id_ex_rs2, id_ex_reg_write, id_ex_mem_write, id_ex_wb_mux_sel}),
		.out({ex_mem_alu_result, ex_mem_write_data, ex_mem_rd, ex_mem_pc_plus_4, ex_mem_funct3, ex_mem_rs2, ex_mem_reg_write, ex_mem_mem_write, ex_mem_wb_mux_sel})
	);
	MEM_Stage mem_stage_inst(
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
	PipelineRegister #(.WIDTH(MEM_WB_WIDTH)) mem_wb_reg(
		.clk(clk),
		.rst(rst),
		.en(1'b1),
		.clear(1'b0),
		.in({mem_read_data, ex_mem_alu_result, ex_mem_rd, ex_mem_pc_plus_4, ex_mem_reg_write, ex_mem_wb_mux_sel}),
		.out({mem_wb_read_data, mem_wb_alu_result, mem_wb_rd, mem_wb_pc_plus_4, mem_wb_reg_write, mem_wb_wb_mux_sel})
	);
	WB_Stage wb_stage_inst(
		.mem_wb_wb_mux_sel(mem_wb_wb_mux_sel),
		.mem_wb_alu_result(mem_wb_alu_result),
		.mem_wb_pc_plus_4(mem_wb_pc_plus_4),
		.dmem_read_data(mem_read_data),
		.wb_write_data(wb_write_data)
	);
endmodule
module PipelineRegister (
	clk,
	rst,
	en,
	clear,
	in,
	out
);
	parameter WIDTH = 32;
	input wire clk;
	input wire rst;
	input wire en;
	input wire clear;
	input wire [WIDTH - 1:0] in;
	output reg [WIDTH - 1:0] out;
	always @(posedge clk) begin : PipelineRegLogic
		if (rst) begin : Reset
			out <= 1'sb0;
		end
		else if (clear) begin : Flush
			out <= 1'sb0;
		end
		else if (en) begin : Update
			out <= in;
		end
	end
endmodule
module RegFile (
	clk,
	rst,
	RegWrite,
	rs1,
	rs2,
	rd,
	write_data,
	read_data1,
	read_data2
);
	input wire clk;
	input wire rst;
	input wire RegWrite;
	input wire [4:0] rs1;
	input wire [4:0] rs2;
	input wire [4:0] rd;
	localparam riscv_pkg_XLEN = 32;
	input wire [31:0] write_data;
	output wire [31:0] read_data1;
	output wire [31:0] read_data2;
	function automatic should_forward;
		input reg [4:0] rs;
		input reg [4:0] rd;
		input reg reg_write;
		should_forward = (reg_write && (rs != 5'b00000)) && (rs == rd);
	endfunction
	localparam riscv_pkg_REG_SIZE = 32;
	reg [31:0] register_memory [0:31];
	function automatic [31:0] read_register;
		input reg [4:0] rs;
		input reg [4:0] rd;
		input reg reg_write;
		input reg [31:0] write_data;
		if (rs == 5'b00000) begin : ReadX0
			read_register = {riscv_pkg_XLEN {1'b0}};
		end
		else if (should_forward(rs, rd, reg_write)) begin : WBForwarding
			read_register = write_data;
		end
		else begin : NormalRead
			read_register = register_memory[rs];
		end
	endfunction
	assign read_data1 = read_register(rs1, rd, RegWrite, write_data);
	assign read_data2 = read_register(rs2, rd, RegWrite, write_data);
	always @(posedge clk) begin : WriteRegister
		if (rst) begin : ResetRegisters
			begin : sv2v_autoblock_1
				reg signed [31:0] i;
				for (i = 0; i < riscv_pkg_REG_SIZE; i = i + 1)
					begin : ZeroReset
						register_memory[i] <= {riscv_pkg_XLEN {1'b0}};
					end
			end
		end
		else if (RegWrite && (rd != 5'b00000)) begin : WriteEnable
			register_memory[rd] <= write_data;
		end
	end
	initial begin : InitRegisters
		begin : sv2v_autoblock_2
			reg signed [31:0] i;
			for (i = 0; i < riscv_pkg_REG_SIZE; i = i + 1)
				begin : ZeroInit
					register_memory[i] = {riscv_pkg_XLEN {1'b0}};
				end
		end
	end
endmodule
module WB_Stage (
	mem_wb_wb_mux_sel,
	mem_wb_alu_result,
	mem_wb_pc_plus_4,
	dmem_read_data,
	wb_write_data
);
	reg _sv2v_0;
	input wire [1:0] mem_wb_wb_mux_sel;
	localparam riscv_pkg_XLEN = 32;
	input wire [31:0] mem_wb_alu_result;
	input wire [31:0] mem_wb_pc_plus_4;
	input wire [31:0] dmem_read_data;
	output reg [31:0] wb_write_data;
	always @(*) begin : WriteBackMUX
		if (_sv2v_0)
			;
		case (mem_wb_wb_mux_sel)
			2'b00: wb_write_data = mem_wb_alu_result;
			2'b01: wb_write_data = dmem_read_data;
			2'b10: wb_write_data = mem_wb_pc_plus_4;
			default: wb_write_data = {riscv_pkg_XLEN {1'b0}};
		endcase
	end
	initial _sv2v_0 = 0;
endmodule
