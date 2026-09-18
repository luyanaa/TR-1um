(* blackbox *)
module tr1um_spitx (GND, VDD, busy, clk, done, mosi, sclk, start, data_in);
 inout GND;
 inout VDD;
 output busy;
 input clk;
 output done;
 output mosi;
 output sclk;
 input start;
 input [7:0] data_in;
endmodule
