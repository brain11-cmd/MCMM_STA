# 毕业设计项目结构说明

## 项目核心文件夹

是的，这三个文件夹都是你毕业设计项目的核心组成部分：

### 1. **OpenTimer** (`D:\opentimer\OpenTimer`)
**作用**: 静态时序分析（STA）工具

**核心内容**:
- `bin/ot-shell` - OpenTimer 可执行文件（用于时序分析）
- `ot/` - OpenTimer 源代码（已修改 `arc.hpp` 添加 delay 访问方法）
- `test_aes.tcl` - AES benchmark 测试脚本示例

**在你的研究中的作用**:
- 执行多 corner 静态时序分析
- 分析 benchmark 设计的时序性能
- 提取时序图数据（节点、边、延迟等）用于 GNN 模型

---

### 2. **benchmark** (`D:\bishe_database\benchmark`)
**作用**: 基准测试设计集合

**核心内容**:
- `rtl_src/` - RTL 源代码（20+ 个 benchmark 设计）
- `netlists/` - 综合后的门级网表（SAED32 RVT 库）
  - `*_netlist.v` - Verilog 网表文件
  - `*.sdc` - 时序约束文件（已优化）
- `scripts/` - 综合和优化脚本
  - `synth_saed32.tcl` - Yosys 综合脚本
  - `quick_optimize.ps1` - 时钟周期优化脚本
  - `fix_ports.py` - 网表修复脚本

**在你的研究中的作用**:
- 提供多个不同规模的测试设计（从简单到复杂）
- 已优化的网表和约束文件，可直接用于时序分析
- 5 个可用的 benchmark：gcd, uart, spi, aes, dynamic_node

---

### 3. **BUFLIB** (`D:\bishe_database\BUFLIB`)
**作用**: 标准单元库文件（Liberty 格式）

**核心内容**:
- `lib_rvt/` - RVT（Regular Vt）阈值电压库
  - **27 个 PVT corners**：
    - **Process**: FF (Fast-Fast), SS (Slow-Slow), TT (Typical-Typical)
    - **Voltage**: 0.7V, 0.75V, 0.78V, 0.85V, 0.95V, 1.05V, 1.16V
    - **Temperature**: -40°C, 25°C, 125°C
    - 组合：3 × 7 × 3 = 63 种组合，但实际有 27 个库文件
- `lib_lvt/` - LVT（Low Vt）阈值电压库
- `lib_hvt/` - HVT（High Vt）阈值电压库

**在你的研究中的作用**:
- 提供多 corner 时序分析所需的库文件
- 每个 corner 包含标准单元的时序、功耗、面积信息
- 用于 OpenTimer 进行多 corner STA

---

## 项目工作流程

```
RTL 源代码 (benchmark/rtl_src/)
    ↓
Yosys 综合 (benchmark/scripts/synth_saed32.tcl)
    ↓
门级网表 (benchmark/netlists/*_netlist.v)
    ↓
OpenTimer 分析 (OpenTimer/bin/ot-shell)
    ↓
时序图数据提取 (用于 GNN 模型)
```

**多 Corner 分析流程**:
```
对于每个 benchmark:
  对于每个 PVT corner (27个):
    加载库文件 (BUFLIB/lib_rvt/*.lib)
    加载网表 (benchmark/netlists/*_netlist.v)
    加载约束 (benchmark/netlists/*.sdc)
    执行时序分析
    提取图数据 (节点、边、特征)
```

---

## 项目数据统计

### Benchmark
- **总数**: 20+ 个设计
- **可用**: 5 个（gcd, uart, spi, aes, dynamic_node）
- **规模**: 从 200 门（gcd）到 10000+ 门（aes）

### PVT Corners
- **RVT 库**: 27 个 corners
- **覆盖**: 3 种工艺角 × 7 种电压 × 3 种温度

### 时序数据
- **每个 benchmark**: 27 corners × 多个时序路径
- **数据量**: 足够用于 GNN 模型训练

---

## 文件组织建议

### 核心文件（必须保留）
- ✅ OpenTimer 源代码和可执行文件
- ✅ benchmark 网表和约束文件
- ✅ BUFLIB 库文件（27 个 corners）
- ✅ 综合和优化脚本

### 可清理的文件
- ⚠️ 临时测试文件（已清理）
- ⚠️ 综合日志文件（可选择性保留）
- ⚠️ 备份文件（可删除）

---

## 总结

**是的，这三个文件夹都是你毕业设计的核心**：

1. **OpenTimer** - 分析工具
2. **benchmark** - 测试数据
3. **BUFLIB** - 库文件

它们共同构成了你的多 corner 静态时序分析研究平台，用于：
- 生成时序图数据
- 训练 GNN 模型
- 进行时序预测和优化

