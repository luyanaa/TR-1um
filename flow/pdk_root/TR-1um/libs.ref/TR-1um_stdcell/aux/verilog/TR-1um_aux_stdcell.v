// Functional models for KoheiUchi/TR_1um_sc auxiliary cells.
`timescale 1ns/1ps
module DFFQU1 (CK, D, Q, VDD, GND);
  input CK, D; output Q; inout VDD, GND; reg q;
  always @(posedge CK) q <= D;
  assign Q = q;
endmodule
module HA1S (A, B, CO, S, VDD, GND);
  input A, B; output CO, S; inout VDD, GND;
  assign S = A ^ B; assign CO = A & B;
endmodule
module FA1D1 (A, CO, B, CI, S, VDD, GND);
  input A, B, CI; output CO, S; inout VDD, GND;
  assign S = A ^ B ^ CI; assign CO = (A & B) | (B & CI) | (A & CI);
endmodule
