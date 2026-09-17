`ifdef SIMULATION
`timescale 1ns/1ps
`endif
module tr1um_irqctrl (
 input wire clk, input wire [3:0] irq, input wire [3:0] mask,
 input wire ack, output wire pending, output reg [1:0] vector,
 inout wire VDD, inout wire GND
);
 wire inactive_reset;
`ifdef SIMULATION
 assign inactive_reset = 1'b0;
`else
 TIELO reset_tie (.LO(inactive_reset));
`endif
 reg [3:0] latched; wire [3:0] active=latched & mask;
 assign pending=|active;
 always @* begin
  if(active[3]) vector=3; else if(active[2]) vector=2; else if(active[1]) vector=1; else vector=0;
 end
 always @(posedge clk or posedge inactive_reset) begin
  if(inactive_reset) latched<=0;
  else begin
   latched<=latched|irq;
   if(ack && pending) begin
    if(vector==0) latched[0]<=0; else if(vector==1) latched[1]<=0; else if(vector==2) latched[2]<=0; else latched[3]<=0;
   end
  end
 end
`ifdef SIMULATION
 initial latched=0;
`endif
endmodule
