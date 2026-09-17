`timescale 1ns/1ps
module tr1um_popcount8_tb;
    reg clk = 0;
    reg [7:0] data_in = 0;
    wire [3:0] count;
    wire VDD, GND;

    tr1um_popcount8 dut (.clk(clk), .data_in(data_in),
                         .count(count), .VDD(VDD), .GND(GND));
    always #5 clk = ~clk;

    task automatic check(input [7:0] value, input [3:0] expected_count);
        begin
            @(negedge clk); data_in = value;
            @(posedge clk); #1;
            if (count !== expected_count)
                $fatal(1, "popcount mismatch for %02x: count=%0d expected=%0d",
                       value, count, expected_count);
        end
    endtask

    initial begin
        check(8'h00, 0);
        check(8'hA5, 4);
        check(8'h7F, 7);
        check(8'hFF, 8);
        check(8'h01, 1);
        $display("PASS tr1um_popcount8");
        $finish;
    end
endmodule
