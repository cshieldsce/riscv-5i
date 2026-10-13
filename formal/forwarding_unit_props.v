// Formal properties for ForwardingUnit (src/forwarding_unit.sv).
// Plain Verilog because sv2v drops assert and cover statements. The DUT is
// the sv2v conversion of the unmodified RTL. ForwardingUnit is purely
// combinational, so every input is left free and the solver checks all of
// the 2^14 input combinations at once.

module forwarding_unit_props (
    input [4:0] id_ex_rs1,
    input [4:0] id_ex_rs2,
    input [4:0] ex_mem_rd,
    input       ex_mem_reg_write,
    input [4:0] mem_wb_rd,
    input       mem_wb_reg_write
);
    wire [1:0] forward_a, forward_b;

    ForwardingUnit dut (
        .id_ex_rs1(id_ex_rs1), .id_ex_rs2(id_ex_rs2),
        .ex_mem_rd(ex_mem_rd), .ex_mem_reg_write(ex_mem_reg_write),
        .mem_wb_rd(mem_wb_rd), .mem_wb_reg_write(mem_wb_reg_write),
        .forward_a(forward_a), .forward_b(forward_b)
    );

    // The specification restated independently of the RTL's helper functions
    function [1:0] spec;
        input [4:0] rs;
        begin
            if (rs != 0 && ex_mem_reg_write && ex_mem_rd == rs)
                spec = 2'b10;
            else if (rs != 0 && mem_wb_reg_write && mem_wb_rd == rs)
                spec = 2'b01;
            else
                spec = 2'b00;
        end
    endfunction

    always @* begin
        // 1. Both outputs match the spec, which covers priority and the double hazard
        assert (forward_a == spec(id_ex_rs1));
        assert (forward_b == spec(id_ex_rs2));

        // 2. x0 is never forwarded
        if (id_ex_rs1 == 0) assert (forward_a == 2'b00);
        if (id_ex_rs2 == 0) assert (forward_b == 2'b00);

        // 3. Nothing is forwarded from a stage that doesn't write
        if (!ex_mem_reg_write) assert (forward_a != 2'b10 && forward_b != 2'b10);
        if (!mem_wb_reg_write) assert (forward_a != 2'b01 && forward_b != 2'b01);

        // 4. 2'b11 is never driven
        assert (forward_a != 2'b11 && forward_b != 2'b11);

        // 5. EX/MEM wins when both stages write the register the operand reads
        if (id_ex_rs1 != 0 && ex_mem_reg_write && mem_wb_reg_write && ex_mem_rd == id_ex_rs1 && mem_wb_rd == id_ex_rs1)
            assert (forward_a == 2'b10);
        if (id_ex_rs2 != 0 && ex_mem_reg_write && mem_wb_reg_write && ex_mem_rd == id_ex_rs2 && mem_wb_rd == id_ex_rs2)
            assert (forward_b == 2'b10);

        // 6. Reachability: each forwarding select can happen, and the double hazard can
        cover (forward_a == 2'b10);
        cover (forward_a == 2'b01);
        cover (forward_b == 2'b10);
        cover (forward_b == 2'b01);
        cover (id_ex_rs1 != 0 && ex_mem_reg_write && mem_wb_reg_write && ex_mem_rd == id_ex_rs1 && mem_wb_rd == id_ex_rs1);
    end
endmodule
