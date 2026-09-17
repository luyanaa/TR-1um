`timescale 1ns/1ps

module tr1um_uarttx_big_tb;
    localparam realtime CLOCK_PERIOD_NS = 67.8168402778;
    localparam realtime BIT_PERIOD_NS   = 8680.55555556;

    reg clk = 1'b0;
    wire tx;
    supply1 VDD;
    supply0 GND;

    tr1um_uarttx_big dut (
        .clk(clk), .tx(tx), .VDD(VDD), .GND(GND)
    );

    always #(CLOCK_PERIOD_NS / 2.0) clk = ~clk;

    function [7:0] expected;
        input integer index;
        begin
            case (index)
                0: expected="S";  1: expected="Y";  2: expected="M";
                3: expected="B";  4: expected="I";  5: expected="O";
                6: expected="T";  7: expected="I";  8: expected="C";
                9: expected="@"; 10: expected="Y"; 11: expected="G";
               12: expected="@"; 13: expected="C"; 14: expected="K";
               15: expected="D"; 16: expected="U"; 17: expected="R";
               18: expected="@"; 19: expected="R"; 20: expected="O";
               21: expected="B"; 22: expected="I"; 23: expected="N";
               default: expected="@";
            endcase
        end
    endfunction

    task receive_byte;
        output [7:0] value;
        integer bit_number;
        begin
            wait (tx === 1'b0);
            #(BIT_PERIOD_NS * 1.5);
            for (bit_number = 0; bit_number < 8; bit_number = bit_number + 1) begin
                value[bit_number] = tx;
                #(BIT_PERIOD_NS);
            end
            if (tx !== 1'b1) begin
                $display("FAIL: invalid stop bit at %0t", $time);
                $finish_and_return(1);
            end
            #(BIT_PERIOD_NS * 6.0);
        end
    endtask

    reg [7:0] received;
    integer byte_number;
    initial begin
        $display("Receiving one 32-character cycle plus the first byte after wrap:");
        for (byte_number = 0; byte_number < 33; byte_number = byte_number + 1) begin
            receive_byte(received);
            if (received !== expected(byte_number % 32)) begin
                $display("\nFAIL: byte %0d was 0x%02x, expected 0x%02x",
                         byte_number, received, expected(byte_number % 32));
                $finish_and_return(1);
            end
            $write("%c", received);
            if ((byte_number % 32) == 31)
                $write("\n");
        end
        $display("PASS");
        $finish;
    end

    initial begin
        #7000000;
        $display("FAIL: simulation timeout");
        $finish_and_return(1);
    end
endmodule
