# The checked-in TR-1um Liberty is placeholder-characterized, so physical-flow
# smoke testing uses the same relaxed period as tr1um_counter. The UART baud
# calculation itself assumes the real applied clock is 14.7456 MHz.
create_clock -period 5000.000 -name clk [get_ports clk]
set_clock_uncertainty 2.000 [get_clocks clk]
set_output_delay -clock clk 2.000 [get_ports tx]
