`ifdef SIMULATION
`timescale 1ns/1ps
`endif
module tr1um_fifo4 (
 input wire clk, input wire push, input wire pop, input wire [3:0] data_in,
 output wire [3:0] data_out, output wire empty, output wire full,
 inout wire VDD, inout wire GND
);
 wire inactive_reset;
`ifdef SIMULATION
 assign inactive_reset = 1'b0;
`else
 TIELO reset_tie (.LO(inactive_reset));
`endif
 reg [3:0] mem0,mem1,mem2,mem3; reg [1:0] rd_ptr,wr_ptr; reg [2:0] count;
 assign empty=(count==0); assign full=(count==4);
 assign data_out = rd_ptr==0 ? mem0 : rd_ptr==1 ? mem1 : rd_ptr==2 ? mem2 : mem3;
 always @(posedge clk or posedge inactive_reset) begin
  if(inactive_reset) begin rd_ptr<=0;wr_ptr<=0;count<=0;mem0<=0;mem1<=0;mem2<=0;mem3<=0; end
  else begin
   if(push && !full) begin
    if(wr_ptr==0) mem0<=data_in; else if(wr_ptr==1) mem1<=data_in; else if(wr_ptr==2) mem2<=data_in; else mem3<=data_in;
    wr_ptr<=wr_ptr+1'b1;
   end
   if(pop && !empty) rd_ptr<=rd_ptr+1'b1;
   case ({push && !full,pop && !empty}) 2'b10:count<=count+1'b1; 2'b01:count<=count-1'b1; default:count<=count; endcase
  end
 end
`ifdef SIMULATION
 initial begin rd_ptr=0;wr_ptr=0;count=0;mem0=0;mem1=0;mem2=0;mem3=0;end
`endif
endmodule
