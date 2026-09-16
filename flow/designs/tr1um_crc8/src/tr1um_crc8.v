`ifdef SIMULATION
`timescale 1ns/1ps
`endif

module tr1um_crc8 (
    input  wire       clk,
    input  wire       valid,
    input  wire       data_in,
    output reg  [7:0] crc,
    inout  wire       VDD,
    inout  wire       GND
);
    wire inactive_reset;
    wire feedback = crc[7] ^ data_in;
    wire [7:0] crc_next = {crc[6:0], 1'b0} ^ (feedback ? 8'h07 : 8'h00);

`ifdef SIMULATION
    assign inactive_reset = 1'b0;
`else
    TIELO reset_tie (.LO(inactive_reset));
`endif

    always @(posedge clk or posedge inactive_reset) begin
        if (inactive_reset)
            crc <= 8'h00;
        else if (valid)
            crc <= crc_next;
    end

`ifdef SIMULATION
    initial crc = 8'h00;
`endif
endmodule
