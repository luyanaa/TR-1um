`ifdef SIMULATION
`timescale 1ns/1ps
`endif

// Compact 24-character TR-1um UART test transmitter.
// Clock: 14.7456 MHz. UART: 115200 baud, 8 data bits, no parity, 1 stop bit.
// Message cycle: "SYMBIOTIC@YG@CKDUR@ROBIN@@@@@@@@".
module tr1um_uarttx_big (
    input  wire clk,
    output reg  tx,
    inout  wire VDD,
    inout  wire GND
);

    // One free-running counter contains the /128 baud divider, sixteen UART
    // slots, and a 0..31 character-time index. Slots 24..31 transmit '@',
    // providing a visible separator without modulo-24 rewind logic.
    reg [15:0] phase;

    // Five-bit alphabet code: A=1 through Z=26, and '@'=0. This is smaller
    // than storing eight-bit ASCII for every character.
    reg [4:0] letter;
    always @* begin
        case (phase[15:11])
            5'd0:  letter = 5'd19; // S
            5'd1:  letter = 5'd25; // Y
            5'd2:  letter = 5'd13; // M
            5'd3:  letter = 5'd2;  // B
            5'd4:  letter = 5'd9;  // I
            5'd5:  letter = 5'd15; // O
            5'd6:  letter = 5'd20; // T
            5'd7:  letter = 5'd9;  // I
            5'd8:  letter = 5'd3;  // C
            5'd9:  letter = 5'd0;  // @
            5'd10: letter = 5'd25; // Y
            5'd11: letter = 5'd7;  // G
            5'd12: letter = 5'd0;  // @
            5'd13: letter = 5'd3;  // C
            5'd14: letter = 5'd11; // K
            5'd15: letter = 5'd4;  // D
            5'd16: letter = 5'd21; // U
            5'd17: letter = 5'd18; // R
            5'd18: letter = 5'd0;  // @
            5'd19: letter = 5'd18; // R
            5'd20: letter = 5'd15; // O
            5'd21: letter = 5'd2;  // B
            5'd22: letter = 5'd9;  // I
            5'd23: letter = 5'd14; // N
            default: letter = 5'd0; // @ in unused slots 24..31
        endcase
    end

    // Uppercase ASCII and '@' are both {1'b0, 1'b1, 1'b0, letter[4:0]}.
    // Select only the bit being transmitted, avoiding a shift register,
    // character register, reduction operators, and unused-slot gating.
    always @* begin
        case (phase[10:7])
            4'd0: tx = 1'b0;       // start
            4'd1: tx = letter[0];
            4'd2: tx = letter[1];
            4'd3: tx = letter[2];
            4'd4: tx = letter[3];
            4'd5: tx = letter[4];
            4'd6: tx = 1'b0;       // ASCII bit 5
            4'd7: tx = 1'b1;       // ASCII bit 6
            4'd8: tx = 1'b0;       // ASCII bit 7
            default: tx = 1'b1;    // stop and padding
        endcase
    end

    // Drive the inactive active-high reset through a physical tie cell.  RST
    // remains an ordinary routed signal; GND is used only as a supply net.
    // Sharing one tie is intentional here because the 16 loads are local and
    // this macro has a strict area target.
    wire inactive_reset;
`ifdef SIMULATION
    assign inactive_reset = 1'b0;
`else
    TIELO reset_tie (.LO(inactive_reset));
`endif

    always @(posedge clk or posedge inactive_reset) begin
        if (inactive_reset)
            phase <= 16'd0;
        else
            phase <= phase + 16'd1;
    end

`ifdef SIMULATION
    initial phase = 16'd0;
`endif

endmodule
