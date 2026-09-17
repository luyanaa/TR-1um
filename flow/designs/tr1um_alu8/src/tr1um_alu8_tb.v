`timescale 1ns/1ps
module tr1um_alu8_tb;
 reg clk=0; reg [7:0] a,b; reg [2:0] op; wire [7:0] y; wire zero,carry; supply1 VDD; supply0 GND;
 tr1um_alu8 dut(clk,a,b,op,y,zero,carry,VDD,GND);
 always #5 clk=~clk;
 task check; input [7:0] aa,bb; input [2:0] oo; input [7:0] yy; begin
  a=aa;b=bb;op=oo; @(posedge clk); #1; if(y!==yy) $fatal(1,"op %0d: %h != %h",oo,y,yy);
 end endtask
 initial begin check(8'd250,8'd10,0,8'd4); check(9,3,1,6); check(8'hac,8'h3c,2,8'h2c); check(8'h80,0,5,0); check(3,7,7,3); $display("PASS tr1um_alu8"); $finish; end
endmodule
