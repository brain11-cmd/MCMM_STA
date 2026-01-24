# SDC for ethmac design
# Clock period: 10ns (100MHz)
create_clock -period 10 -name wb_clk_i [get_ports wb_clk_i]

# Input constraints
set_input_delay 0 -clock wb_clk_i [all_inputs]
set_input_transition 0.1 [all_inputs]

# Output constraints  
set_output_delay 0 -clock wb_clk_i [all_outputs]
set_load 0.01 [all_outputs]




