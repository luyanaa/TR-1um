`timescale 1ns/1ps
module tr1um_irqctrl_tb;
 reg clk=0,ack=0; reg [3:0] irq=0,mask=15; wire pending; wire [1:0] vector; supply1 VDD; supply0 GND;
 tr1um_irqctrl dut(clk,irq,mask,ack,pending,vector,VDD,GND); always #5 clk=~clk;
 initial begin @(negedge clk);irq=4'b1010;@(negedge clk);irq=0;#1;if(!pending||vector!=3)$fatal;ack=1;@(negedge clk);ack=0;#1;if(!pending||vector!=1)$fatal;ack=1;@(negedge clk);ack=0;#1;if(pending)$fatal;$display("PASS tr1um_irqctrl");$finish;end
endmodule
