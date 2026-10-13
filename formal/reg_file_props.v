// Formal properties for RegFile (src/reg_file.sv). Plain Verilog because
// sv2v drops assert and cover statements.
// One register is picked by the solver (anyconst) and followed with a shadow
// copy, so the proof covers every register without a 32-way unroll. The
// read data is checked against the shadow on both read ports every cycle.

module reg_file_props (
    input        clk,
    input        rst,
    input        RegWrite,
    input [4:0]  rs1,
    input [4:0]  rs2,
    input [4:0]  rd,
    input [31:0] write_data
);
    wire [31:0] read_data1, read_data2;

    RegFile dut (
        .clk(clk), .rst(rst), .RegWrite(RegWrite),
        .rs1(rs1), .rs2(rs2), .rd(rd), .write_data(write_data),
        .read_data1(read_data1), .read_data2(read_data2)
    );

    (* anyconst *) wire [4:0] chk;
    reg [31:0] shadow = 32'b0;     // what register chk should hold, RegFile zeroes at start

    always @(posedge clk) begin
        if (rst)
            shadow <= 32'b0;
        else if (RegWrite && rd == chk && chk != 5'b0)
            shadow <= write_data;
    end

    // What a read of chk has to return: x0 is zero, a write in the same cycle
    // is passed straight through (even during reset, the RTL doesn't look at
    // rst there), otherwise the stored value
    wire [31:0] expected = (chk == 5'b0)            ? 32'b0 :
                           (RegWrite && rd == chk)  ? write_data :
                                                      shadow;

    always @* begin
        // 1. Read ports follow the model for the chosen register
        if (rs1 == chk) assert (read_data1 == expected);
        if (rs2 == chk) assert (read_data2 == expected);

        // 2. x0 reads zero on both ports whatever is being written
        if (rs1 == 5'b0) assert (read_data1 == 32'b0);
        if (rs2 == 5'b0) assert (read_data2 == 32'b0);
    end
endmodule
