`timescale 1ns/1ps
module tr1um_busdecode_tb;
 reg clk=0,enable=0;reg[2:0]address=0;wire[7:0]select;wire any;supply1 VDD;supply0 GND;
 tr1um_busdecode dut(clk,enable,address,select,any,VDD,GND);always #5 clk=~clk;
 initial begin @(negedge clk);enable=1;address=5;@(negedge clk);#1;if(select!==8'b00100000||!any)$fatal;enable=0;@(negedge clk);#1;if(select!==0||any)$fatal;$display("PASS tr1um_busdecode");$finish;end
endmodule
