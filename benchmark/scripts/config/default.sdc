# Default SDC constraints for synthesis
# 默认时钟周期 10ns (100MHz)
create_clock -name clk -period 10.0 [get_ports clk*]

# 输入延迟
set_input_delay -clock clk 2.0 [all_inputs]

# 输出延迟
set_output_delay -clock clk 2.0 [all_outputs]

# 驱动强度和负载
set_driving_cell -lib_cell INVX1_HVT [all_inputs]
set_load 0.01 [all_outputs]




