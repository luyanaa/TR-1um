`ifdef SIMULATION
`timescale 1ns/1ps
`endif
module tr1um_spitx (
 input wire clk, input wire start, input wire [7:0] data_in,
 output wire sclk, output wire mosi, output wire busy, output reg done,
 inout wire VDD, inout wire GND
);
 wire inactive_reset;
`ifdef SIMULATION
 assign inactive_reset = 1'b0;
`else
 TIELO reset_tie (.LO(inactive_reset));
`endif
 reg [7:0] shift; reg [2:0] bit_count; reg phase; reg active;
 assign busy=active; assign sclk=active && phase; assign mosi=shift[7];
 always @(posedge clk or posedge inactive_reset) begin
  if(inactive_reset) begin shift<=0;bit_count<=0;phase<=0;active<=0;done<=0; end
  else begin
   done<=0;
   if(start && !active) begin shift<=data_in;bit_count<=0;phase<=0;active<=1; end
   else if(active) begin
    phase<=~phase;
    if(phase) begin shift<={shift[6:0],1'b0}; if(bit_count==7) begin active<=0;done<=1;phase<=0;end else bit_count<=bit_count+1'b1; end
   end
  end
 end
`ifdef SIMULATION
 initial begin shift=0;bit_count=0;phase=0;active=0;done=0;end
`endif
endmodule
