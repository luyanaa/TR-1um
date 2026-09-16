`timescale 1ns/1ps
module tr1um_spitx_tb;
 reg clk=0,start=0;reg [7:0] din=0;wire sclk,mosi,busy,done;supply1 VDD;supply0 GND;integer cycles=0;
 tr1um_spitx dut(clk,start,din,sclk,mosi,busy,done,VDD,GND);always #5 clk=~clk;
 initial begin @(negedge clk);din=8'ha5;start=1;@(negedge clk);start=0; while(!done)begin @(negedge clk);cycles=cycles+1;if(cycles>20)$fatal;end if(busy)$fatal;$display("PASS tr1um_spitx");$finish;end
endmodule
