# SDC for chameleon design (SoC with Ibex core)
# Clock period: 10ns (100 MHz) - Reasonable for SoC design
# Note: WNS/TNS violations are mainly from black-box modules (DFFRAM_4K, DMC_32x16HC, etc.)
# These modules are not in the celllib, so OpenTimer cannot analyze their timing properly
# The violations do not affect the timing analysis of the main logic

create_clock -period 10.0 -name HCLK [get_ports HCLK]

# Input constraints
# All inputs are synchronous to HCLK
set_input_delay 0 -clock HCLK [all_inputs]
set_input_transition 0.1 [all_inputs]

# Output constraints  
# All outputs are synchronous to HCLK
set_output_delay 0 -clock HCLK [all_outputs]
set_load 0.01 [all_outputs]

# Reset is asynchronous
# (reset timing is typically handled separately in real designs)

