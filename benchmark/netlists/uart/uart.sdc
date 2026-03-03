# SDC for uart design
# Clock period: 0.15ns (Optimized from 10ns, 6666.67 MHz)
create_clock -period 0.15 -name clk [get_ports clk]

# Input constraints
set_input_delay 0 -clock clk [all_inputs]
set_input_transition 0.1 [all_inputs]

# Output constraints  
set_output_delay 0 -clock clk [all_outputs]
set_load 0.01 [all_outputs]





