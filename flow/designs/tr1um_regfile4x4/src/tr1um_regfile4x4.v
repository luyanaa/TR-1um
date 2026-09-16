`ifdef SIMULATION
`timescale 1ns/1ps
`endif

module tr1um_regfile4x4 (
    input  wire       clk,
    input  wire       write_enable,
    input  wire [1:0] write_addr,
    input  wire [1:0] read_addr,
    input  wire [3:0] write_data,
    output wire [3:0] read_data,
    inout  wire       VDD,
    inout  wire       GND
);
    wire inactive_reset;
    reg [3:0] memory [0:3];
    integer i;

`ifdef SIMULATION
    assign inactive_reset = 1'b0;
`else
    TIELO reset_tie (.LO(inactive_reset));
`endif

    assign read_data = memory[read_addr];

    always @(posedge clk or posedge inactive_reset) begin
        if (inactive_reset) begin
            for (i = 0; i < 4; i = i + 1)
                memory[i] <= 4'h0;
        end else if (write_enable) begin
            memory[write_addr] <= write_data;
        end
    end

`ifdef SIMULATION
    initial begin
        for (i = 0; i < 4; i = i + 1)
            memory[i] = 4'h0;
    end
`endif
endmodule
