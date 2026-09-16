`timescale 1ns/1ps
module tr1um_fsm_lock_tb;
    reg clk = 0;
    reg enable = 0;
    reg code_bit = 0;
    wire unlocked, busy;
    wire VDD, GND;

    tr1um_fsm_lock dut (.clk(clk), .enable(enable), .code_bit(code_bit),
                        .unlocked(unlocked), .busy(busy), .VDD(VDD), .GND(GND));
    always #5 clk = ~clk;

    task automatic send_bit(input value);
        begin
            @(negedge clk); enable = 1; code_bit = value;
            @(posedge clk); #1;
        end
    endtask

    initial begin
        send_bit(1); send_bit(0); send_bit(1); send_bit(0);
        if (unlocked) $fatal(1, "wrong sequence unlocked FSM");
        send_bit(1); send_bit(0); send_bit(1); send_bit(1);
        if (!unlocked) $fatal(1, "1011 sequence was not recognized");
        @(negedge clk); enable = 0;
        @(posedge clk); #1;
        if (unlocked) $fatal(1, "unlock pulse lasted too long");
        $display("PASS tr1um_fsm_lock");
        $finish;
    end
endmodule
