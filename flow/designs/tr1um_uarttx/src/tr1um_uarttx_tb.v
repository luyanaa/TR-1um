`timescale 1ns/1ps

module tr1um_uarttx_tb;
    localparam realtime CLOCK_PERIOD_NS = 33.9084201389;
    localparam realtime BIT_PERIOD_NS   = 8680.55555556;

    reg clk = 1'b0;
    wire tx;
    supply1 VDD;
    supply0 GND;

    tr1um_uarttx dut (
        .clk(clk),
        .tx(tx),
        .VDD(VDD),
        .GND(GND)
    );

    always #(CLOCK_PERIOD_NS / 2.0) clk = ~clk;

    function [7:0] expected;
        input [1:0] index;
        begin
            case (index)
                2'd0: expected = "U";
                2'd1: expected = "A";
                2'd2: expected = "R";
                default: expected = "T";
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
        $display("Receiving 32 compact-pattern bytes at 115200 baud:");
        for (byte_number = 0; byte_number < 32; byte_number = byte_number + 1) begin
            receive_byte(received);
            if (received !== expected(byte_number[1:0])) begin
                $display("\nFAIL: byte %0d was 0x%02x, expected 0x%02x",
                         byte_number, received, expected(byte_number[1:0]));
                $finish_and_return(1);
            end
            $write("%c", received);
        end
        $display("\nPASS");
        $finish;
    end

    initial begin
        #5000000;
        $display("FAIL: simulation timeout");
        $finish_and_return(1);
    end
endmodule
