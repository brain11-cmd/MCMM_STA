# SDC for riscv32i design (RISC-V 32-bit Integer Core)
# Clock period: 10ns (100 MHz) - Conservative for initial timing analysis
# RISC-V processors typically run at 50-500 MHz in real designs
# Using 100 MHz (10ns) provides good timing margin for STA validation

create_clock -period 10.0 -name clk [get_ports clk]

# Input constraints
# All inputs are synchronous to clk
# Input delay: 0 means inputs arrive at clock edge (ideal case)
set_input_delay 0 -clock clk [all_inputs]
set_input_transition 0.1 [all_inputs]

# Output constraints  
# All outputs are synchronous to clk
# Output delay: 0 means outputs must be ready at clock edge (ideal case)
set_output_delay 0 -clock clk [all_outputs]
set_load 0.01 [all_outputs]

# Reset is asynchronous, but we still constrain it
# (reset timing is typically handled separately in real designs)
# Note: reset timing constraints would be added in production SDC

