`ifdef SIMULATION
`timescale 1ns/1ps
`endif
module tr1um_busdecode (
 input wire clk, input wire enable, input wire [2:0] address,
 output reg [7:0] select, output wire any,
 inout wire VDD, inout wire GND
);
 wire inactive_reset;
`ifdef SIMULATION
 assign inactive_reset = 1'b0;
`else
 TIELO reset_tie (.LO(inactive_reset));
`endif
 reg enable_q; reg [2:0] address_q;
 assign any = |select;
 always @(posedge clk or posedge inactive_reset) begin
  if(inactive_reset) begin enable_q<=0; address_q<=0; end
  else begin enable_q<=enable; address_q<=address; end
 end
 always @* begin
  select=8'b0;
  if(enable_q) begin
   case(address_q)
    0:select[0]=1; 1:select[1]=1; 2:select[2]=1; 3:select[3]=1;
    4:select[4]=1; 5:select[5]=1; 6:select[6]=1; default:select[7]=1;
   endcase
  end
 end
`ifdef SIMULATION
 initial begin enable_q=0;address_q=0;end
`endif
endmodule
