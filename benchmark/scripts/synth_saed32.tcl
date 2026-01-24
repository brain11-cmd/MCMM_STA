# ============================================================================
# SAED32 Yosys Synthesis Script for MCMM STA
# 用于将 RTL 综合到 SAED32 门级网表
# ============================================================================

# 参数设置 (通过命令行传入)
# DESIGN_NAME: 设计名称
# RTL_FILE: RTL 源文件路径
# LIB_FILE: Liberty 库文件路径
# OUTPUT_DIR: 输出目录

# 读取 RTL
read_verilog $::env(RTL_FILE)

# 设置顶层模块
hierarchy -check -top $::env(DESIGN_NAME)

# 高级综合优化
proc -auto

# ============================================================================
# 关键修改：处理 Memory
# ============================================================================
# 将 memory 转换为 DFF (必须在 techmap 之前)
memory -nomap          # 识别 memory
memory_dff             # 将 memory 读写转为 DFF
memory_map             # 将 memory 数组展开为 DFF 阵列

# 转换为 AIG (And-Inverter Graph)
flatten
opt -full
techmap

# 映射 DFF 到库单元
dfflibmap -liberty $::env(LIB_FILE)

# ABC 综合 - 使用 Liberty 库进行技术映射
abc -liberty $::env(LIB_FILE)

# 清理
opt_clean -purge
clean

# 展开总线端口为单 bit 端口 (OpenTimer 需要)
splitnets -ports

# 检查
check

# 写出网表 (splitnets 后会有 escaped identifiers，需要后处理)
write_verilog -noattr -noexpr -nohex $::env(OUTPUT_FILE)

# 统计信息
stat -liberty $::env(LIB_FILE)

puts "============================================"
puts "Synthesis completed for $::env(DESIGN_NAME)"
puts "Output: $::env(OUTPUT_FILE)"
puts "============================================"




