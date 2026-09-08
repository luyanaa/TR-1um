// Mixed hard-macro smoke top for the TR-1um LibreLane flow.
//
// TELESCOPIC_OTA is intentionally power-free here.  The source netlist names
// VDD/0, while ALIGN's generated top-level LEF contract has no corresponding
// pins; this repository snapshot contains no finalized top-level LEF/GDS.
// VDD/GND below power only the standard-cell boundary buffers; macro PDN
// hookup is deferred until qualified physical views are supplied.
module tele_ota_smoke (
    input  wire VBIASN,
    input  wire VBIASP1,
    input  wire VBIASP2,
    input  wire VINN,
    input  wire VINP,
    input  wire ID,
    inout  wire VDD,
    inout  wire GND,
    output wire VOUTN,
    output wire VOUTP
);
    wire ota_voutn;
    wire ota_voutp;

    TELESCOPIC_OTA u_ota (
        .VBIASN(VBIASN),
        .VBIASP1(VBIASP1),
        .VBIASP2(VBIASP2),
        .VINN(VINN),
        .VINP(VINP),
        .VOUTN(ota_voutn),
        .VOUTP(ota_voutp),
        .ID(ID)
    );

    // Digital boundary only: no analog hierarchy is placed in std-cell rows.
    BUF_X1 u_buf_n (
        .VDD(VDD), .GND(GND), .A(ota_voutn), .Y(VOUTN)
    );
    BUF_X1 u_buf_p (
        .VDD(VDD), .GND(GND), .A(ota_voutp), .Y(VOUTP)
    );
endmodule
