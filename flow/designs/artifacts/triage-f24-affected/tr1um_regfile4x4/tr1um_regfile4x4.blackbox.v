(* blackbox *)
module tr1um_regfile4x4 (GND, VDD, clk, write_enable, read_addr, read_data, write_addr, write_data);
 inout GND;
 inout VDD;
 input clk;
 input write_enable;
 input [1:0] read_addr;
 output [3:0] read_data;
 input [1:0] write_addr;
 input [3:0] write_data;
endmodule
