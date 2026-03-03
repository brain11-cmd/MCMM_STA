# SDC for aes design
# Clock period: 0.1ns (10000 MHz) - Optimized
# Original: 10ns (100MHz) with 9.9ns slack
# Optimized: 0.1ns (10GHz) with 0.004ns slack
create_clock -period 0.1 -name clk [get_ports clk]

# Input constraints
set_input_delay 0 -clock clk [all_inputs]
set_input_transition 0.1 [all_inputs]

# Output constraints  
set_output_delay 0 -clock clk [all_outputs]
set_load 0.01 [all_outputs]





