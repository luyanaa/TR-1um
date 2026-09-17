`timescale 1ns/1ps
module tr1um_crc8_tb;
    reg clk = 0;
    reg valid = 0;
    reg data_in = 0;
    wire [7:0] crc;
    wire VDD, GND;
    reg [7:0] expected = 0;
    integer i;
    reg [15:0] pattern = 16'hA35C;

    tr1um_crc8 dut (.clk(clk), .valid(valid), .data_in(data_in),
                    .crc(crc), .VDD(VDD), .GND(GND));
    always #5 clk = ~clk;

    function automatic [7:0] advance_crc(input [7:0] old_crc, input bit_value);
        reg feedback;
        begin
            feedback = old_crc[7] ^ bit_value;
            advance_crc = {old_crc[6:0], 1'b0} ^ (feedback ? 8'h07 : 8'h00);
        end
    endfunction

    initial begin
        for (i = 15; i >= 0; i = i - 1) begin
            @(negedge clk); valid = 1; data_in = pattern[i];
            expected = advance_crc(expected, pattern[i]);
            @(posedge clk); #1;
            if (crc !== expected) $fatal(1, "CRC mismatch at bit %0d", i);
        end
        @(negedge clk); valid = 0; data_in = 1;
        @(posedge clk); #1;
        if (crc !== expected) $fatal(1, "CRC changed while valid was low");
        $display("PASS tr1um_crc8 crc=%02x", crc);
        $finish;
    end
endmodule
