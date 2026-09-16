`timescale 1ns/1ps
module tr1um_regfile4x4_tb;
    reg clk = 0;
    reg write_enable = 0;
    reg [1:0] write_addr = 0;
    reg [1:0] read_addr = 0;
    reg [3:0] write_data = 0;
    wire [3:0] read_data;
    wire VDD, GND;
    integer i;

    tr1um_regfile4x4 dut (
        .clk(clk), .write_enable(write_enable), .write_addr(write_addr),
        .read_addr(read_addr), .write_data(write_data), .read_data(read_data),
        .VDD(VDD), .GND(GND));
    always #5 clk = ~clk;

    initial begin
        for (i = 0; i < 4; i = i + 1) begin
            @(negedge clk);
            write_enable = 1; write_addr = i[1:0]; write_data = (i + 1) * 3;
            @(posedge clk); #1;
        end
        @(negedge clk); write_enable = 0;
        for (i = 0; i < 4; i = i + 1) begin
            read_addr = i[1:0]; #1;
            if (read_data !== ((i + 1) * 3))
                $fatal(1, "register %0d mismatch", i);
        end
        $display("PASS tr1um_regfile4x4");
        $finish;
    end
endmodule
