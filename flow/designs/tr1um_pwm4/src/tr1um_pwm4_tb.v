`timescale 1ns/1ps
module tr1um_pwm4_tb;
    reg clk = 0;
    reg enable = 0;
    reg [3:0] duty = 0;
    wire pwm, wrap;
    wire VDD, GND;
    integer i;
    integer high_count = 0;
    integer wrap_count = 0;

    tr1um_pwm4 dut (.clk(clk), .enable(enable), .duty(duty), .pwm(pwm),
                    .wrap(wrap), .VDD(VDD), .GND(GND));
    always #5 clk = ~clk;

    initial begin
        @(negedge clk); duty = 4'd5; enable = 1;
        for (i = 0; i < 16; i = i + 1) begin
            #1;
            if (pwm) high_count = high_count + 1;
            if (wrap) wrap_count = wrap_count + 1;
            @(negedge clk);
        end
        if (high_count != 5) $fatal(1, "PWM high count=%0d", high_count);
        if (wrap_count != 1) $fatal(1, "wrap count=%0d", wrap_count);
        enable = 0;
        @(posedge clk); #1;
        if (pwm || wrap) $fatal(1, "disabled PWM not low");
        $display("PASS tr1um_pwm4");
        $finish;
    end
endmodule
