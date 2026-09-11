// Black-box logical view for the ALIGN hard macro handoff.
//
// The current repository ALIGN snapshot contains the source/topology and
// primitive LEF collateral, but no finalized top-level TELESCOPIC_OTA GDS or
// top-level LEF.  ALIGN's generated top-level LEF contract has no VDD/0 pins,
// even though the source netlist names VDD and 0.  Keep this module power-free
// for the first mixed-flow smoke; PDN hookup is therefore deferred.
(* blackbox *)
module TELESCOPIC_OTA (
    inout wire VBIASN,
    inout wire VBIASP1,
    inout wire VBIASP2,
    inout wire VINN,
    inout wire VINP,
    inout wire VOUTN,
    inout wire VOUTP,
    inout wire ID
);
endmodule
