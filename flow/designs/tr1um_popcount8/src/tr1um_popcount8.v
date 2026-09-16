`ifdef SIMULATION
`timescale 1ns/1ps
`endif

module tr1um_popcount8 (
    input  wire       clk,
    input  wire [7:0] data_in,
    output reg  [3:0] count,
    inout  wire       VDD,
    inout  wire       GND
);
    wire inactive_reset;
    wire [3:0] count_comb;
    wire [7:0] pair_count;
    wire [2:0] low_count;
    wire [2:0] high_count;

`ifdef SIMULATION
    assign inactive_reset = 1'b0;
`else
    TIELO reset_tie (.LO(inactive_reset));
`endif

    genvar pair_index;
    generate
        for (pair_index = 0; pair_index < 4; pair_index = pair_index + 1) begin : make_pair_count
            assign pair_count[2*pair_index +: 2] =
                data_in[2*pair_index] + data_in[2*pair_index + 1];
        end
    endgenerate

    assign low_count  = pair_count[1:0] + pair_count[3:2];
    assign high_count = pair_count[5:4] + pair_count[7:6];
    assign count_comb = low_count + high_count;
    always @(posedge clk or posedge inactive_reset) begin
        if (inactive_reset) begin
            count <= 4'd0;
        end else begin
            count <= count_comb;
        end
    end

`ifdef SIMULATION
    initial count = 4'd0;
`endif
endmodule
