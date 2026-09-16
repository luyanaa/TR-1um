`ifdef SIMULATION
`timescale 1ns/1ps
`endif

// Compact TR-1um UART test transmitter.
// Clock: 29.4912 MHz. UART: 115200 baud, 8 data bits, no parity, 1 stop bit.
// The logical 32-character test message is "UART" repeated eight times.
module tr1um_uarttx (
    input  wire clk,
    output reg  tx,
    inout  wire VDD,
    inout  wire GND
);

    // One binary counter performs all sequencing:
    //   [7:0]   divide 29.4912 MHz by 256
    //   [11:8]  one of sixteen baud slots per character
    //   [13:12] character in the repeating "UART" pattern
    // Slots 0..9 are start, eight data bits (LSB first), and stop. Slots
    // 10..15 are idle-high padding, making every character exactly 16 bits.
    reg [13:0] phase;

    // Uppercase ASCII is {1'b0, 2'b10, letter[4:0]}. Decode only the bit
    // currently being transmitted; no character register or shift register
    // is required. Letter codes are U=21, A=1, R=18, T=20.
    always @* begin
        case (phase[11:8])
            4'd0: tx = 1'b0;                         // start
            4'd1: tx = ~phase[13];                   // ASCII bit 0
            4'd2: tx = phase[13] & ~phase[12];       // ASCII bit 1
            4'd3: tx = ~(phase[13] ^ phase[12]);     // ASCII bit 2
            4'd4: tx = 1'b0;                         // ASCII bit 3
            4'd5: tx = phase[13] | ~phase[12];       // ASCII bit 4
            4'd6: tx = 1'b0;                         // ASCII bit 5
            4'd7: tx = 1'b1;                         // ASCII bit 6
            4'd8: tx = 1'b0;                         // ASCII bit 7
            default: tx = 1'b1;                      // stop and padding
        endcase
    end

    // GND is the inactive active-high reset connection used to map state to
    // the available TR-1um DFFR cell without adding another signal pin.
    always @(posedge clk or posedge GND) begin
        if (GND)
            phase <= 14'd0;
        else
            phase <= phase + 14'd1;
    end

`ifdef SIMULATION
    initial phase = 14'd0;
`endif

endmodule
