`ifdef SIMULATION
`timescale 1ns/1ps
`endif

module tr1um_pwm4 (
    input  wire       clk,
    input  wire       enable,
    input  wire [3:0] duty,
    output wire       pwm,
    output wire       wrap,
    inout  wire       VDD,
    inout  wire       GND
);
    wire inactive_reset;
    reg [3:0] count;

`ifdef SIMULATION
    assign inactive_reset = 1'b0;
`else
    TIELO reset_tie (.LO(inactive_reset));
`endif

    assign pwm = enable && (count < duty);
    assign wrap = enable && (&count);

    always @(posedge clk or posedge inactive_reset) begin
        if (inactive_reset)
            count <= 4'h0;
        else if (enable)
            count <= count + 1'b1;
        else
            count <= 4'h0;
    end

`ifdef SIMULATION
    initial count = 4'h0;
`endif
endmodule
