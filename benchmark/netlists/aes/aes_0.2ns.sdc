# SDC for aes design - Optimized for 0.2ns (5000 MHz)
create_clock -period 0.2 -name clk [get_ports clk]

# Input constraints
set_input_delay 0 -clock clk [all_inputs]
set_input_transition 0.1 [all_inputs]

# Output constraints  
set_output_delay 0 -clock clk [all_outputs]
set_load 0.01 [all_outputs]

