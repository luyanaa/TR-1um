// Mixed-signal counter template: digital counter plus a fixed analog hard leaf.
// The analog leaf is a connectivity-bearing TR-1um PCell-derived macro.
module tr1um_mixed_counter (
    input  wire clk,
    input  wire rst,
    inout  wire VDD,
    inout  wire GND,
    inout  wire ANA_DA,
    inout  wire ANA_DB,
    inout  wire ANA_SA,
    inout  wire ANA_SB,
    inout  wire ANA_G,
    output wire [3:0] count,
    output wire odd,
    output wire almost_max
);
    reg [3:0] count_r;

    always @(posedge clk or posedge rst) begin
        if (rst)
            count_r <= 4'b0;
        else
            count_r <= count_r + 1'b1;
    end

    assign count = count_r;
    assign odd = count_r[0] ^ count_r[1] ^ count_r[2] ^ count_r[3];
    assign almost_max = &count_r;

    CMC_S_NMOS_B_X1_Y1 u_ana (
        .DA(ANA_DA),
        .DB(ANA_DB),
        .SA(ANA_SA),
        .SB(ANA_SB),
        .G(ANA_G),
        .GND(GND)
    );
endmodule
