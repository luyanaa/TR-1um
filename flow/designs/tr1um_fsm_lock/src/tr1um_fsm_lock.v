`ifdef SIMULATION
`timescale 1ns/1ps
`endif

module tr1um_fsm_lock (
    input  wire clk,
    input  wire enable,
    input  wire code_bit,
    output reg  unlocked,
    output wire busy,
    inout  wire VDD,
    inout  wire GND
);
    localparam [2:0] IDLE = 3'd0, GOT1 = 3'd1, GOT10 = 3'd2,
                     GOT101 = 3'd3, OPEN = 3'd4;
    wire inactive_reset;
    reg [2:0] state;
    reg [2:0] next_state;

`ifdef SIMULATION
    assign inactive_reset = 1'b0;
`else
    TIELO reset_tie (.LO(inactive_reset));
`endif

    assign busy = (state != IDLE);

    always @* begin
        next_state = state;
        case (state)
            IDLE:   if (code_bit)  next_state = GOT1;
            GOT1:   if (!code_bit) next_state = GOT10;
                    else           next_state = GOT1;
            GOT10:  if (code_bit)  next_state = GOT101;
                    else           next_state = IDLE;
            GOT101: if (code_bit)  next_state = OPEN;
                    else           next_state = GOT10;
            OPEN:                  next_state = IDLE;
            default:               next_state = IDLE;
        endcase
    end

    always @(posedge clk or posedge inactive_reset) begin
        if (inactive_reset) begin
            state <= IDLE;
            unlocked <= 1'b0;
        end else begin
            unlocked <= 1'b0;
            if (enable) begin
                state <= next_state;
                if (next_state == OPEN)
                    unlocked <= 1'b1;
            end
        end
    end

`ifdef SIMULATION
    initial begin state = IDLE; unlocked = 1'b0; end
`endif
endmodule
