`timescale 1ns/1ps
module tr1um_fifo4_tb;
 reg clk=0,push=0,pop=0; reg [3:0] din=0; wire [3:0] dout; wire empty,full; supply1 VDD; supply0 GND;
 tr1um_fifo4 dut(clk,push,pop,din,dout,empty,full,VDD,GND); always #5 clk=~clk;
 task put; input [3:0] v; begin @(negedge clk);din=v;push=1;@(negedge clk);push=0;end endtask
 task get; input [3:0] v; begin @(negedge clk); if(dout!==v)$fatal(1,"fifo %h != %h",dout,v);pop=1;@(negedge clk);pop=0;end endtask
 initial begin if(!empty)$fatal; put(1);put(2);put(3);put(4); if(!full)$fatal; get(1);get(2);get(3);get(4); if(!empty)$fatal; $display("PASS tr1um_fifo4");$finish;end
endmodule
