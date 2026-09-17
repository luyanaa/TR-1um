`ifdef SIMULATION
`timescale 1ns/1ps
`endif
module tr1um_alu8 (
    input wire clk, input wire [7:0] a, input wire [7:0] b,
    input wire [2:0] op, output reg [7:0] y,
    output reg zero, output reg carry, inout wire VDD, inout wire GND
);
    wire inactive_reset;
`ifdef SIMULATION
    assign inactive_reset = 1'b0;
`else
    TIELO reset_tie (.LO(inactive_reset));
`endif
    reg [8:0] result;
    always @* begin
        result = 9'd0;
        case (op)
            3'd0: result = {1'b0,a} + {1'b0,b};
            3'd1: result = {1'b0,a} - {1'b0,b};
            3'd2: result = {1'b0,(a & b)};
            3'd3: result = {1'b0,(a | b)};
            3'd4: result = {1'b0,(a ^ b)};
            3'd5: result = {a[7],a[6:0],1'b0};
            3'd6: result = {1'b0,1'b0,a[7:1]};
            default: result = {1'b0,(a < b ? a : b)};
        endcase
    end
    always @(posedge clk or posedge inactive_reset) begin
        if (inactive_reset) begin y <= 0; zero <= 1; carry <= 0; end
        else begin y <= result[7:0]; zero <= ~|result[7:0]; carry <= result[8]; end
    end
`ifdef SIMULATION
    initial begin y=0; zero=1; carry=0; end
`endif
endmodule
