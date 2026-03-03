# SDC for tinyRocket design (Rocket Chip Tiny Config)
# Clock period: 10ns (100 MHz) - Reasonable for CPU design

create_clock -period 10.0 -name clock [get_ports clock]

# Input constraints
# All inputs are synchronous to clock
set_input_delay 0 -clock clock [all_inputs]
set_input_transition 0.1 [all_inputs]

# Output constraints  
# All outputs are synchronous to clock
set_output_delay 0 -clock clock [all_outputs]
set_load 0.01 [all_outputs]

# Reset is asynchronous
# (reset timing is typically handled separately in real designs)























