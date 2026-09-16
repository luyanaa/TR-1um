create_clock -period 5000.000 -name clk [get_ports clk]
set_clock_uncertainty 2.000 [get_clocks clk]
set_input_delay -clock clk 2.000 [all_inputs]
set_output_delay -clock clk 2.000 [all_outputs]
