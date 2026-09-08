// TR-1um test design: 4-bit up counter + combinational outputs.
// Uses only TR-1um_stdcell cells (INV, NAND, NOR, XOR, DFFR).
// The TR-1um DFFR has an active-HIGH async reset.
module tr1um_counter (
    input  wire clk,
    input  wire rst,
    inout  wire VDD,
    inout  wire GND,
    output wire [3:0] count,
    output wire odd,
    output wire almost_max
);
    reg [3:0] count_r;

    always @(posedge clk or posedge rst) begin
        if (rst)
            count_r <= 4'b0;
        else
            count_r <= count_r + 1'b1;
    end

    assign count = count_r;
    assign odd = count_r[0] ^ count_r[1] ^ count_r[2] ^ count_r[3];
    assign almost_max = count_r[3] & count_r[2] & count_r[1] & count_r[0];
endmodule
