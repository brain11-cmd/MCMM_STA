# Multi-Corner Static Timing Analysis for GNN-based Timing Prediction

## 项目简介

本项目使用 OpenTimer 进行多 corner 静态时序分析，提取时序图数据用于图神经网络（GNN）模型训练。

## 项目结构

```
bishe_database/
├── benchmark/          # 基准测试设计
│   ├── rtl_src/       # RTL 源代码
│   ├── netlists/      # 综合后的门级网表
│   └── scripts/       # 综合和优化脚本
├── BUFLIB/            # SAED32 标准单元库
│   ├── lib_rvt/       # RVT 库（27 个 PVT corners）
│   ├── lib_lvt/       # LVT 库
│   └── lib_hvt/       # HVT 库
└── OpenTimer/         # OpenTimer 时序分析工具（子模块）

opentimer/
└── OpenTimer/         # OpenTimer 源代码（已修改）
    ├── bin/           # 可执行文件
    └── ot/             # 源代码（已修改 arc.hpp）
```

## 核心功能

1. **多 Corner 时序分析**: 在 27 个 PVT corners 下分析设计
2. **时序图提取**: 提取节点、边和特征用于 GNN
3. **时钟优化**: 自动优化时钟周期配置

## 可用的 Benchmark

- ✅ gcd (1.0 ns, 1000 MHz)
- ✅ uart (0.15 ns, 6667 MHz)
- ✅ spi (0.15 ns, 6667 MHz)
- ✅ aes (0.1 ns, 10000 MHz)
- ✅ dynamic_node (10 ns, 100 MHz)

## 使用方法

### 1. 综合 Benchmark
```powershell
cd benchmark\scripts
powershell -ExecutionPolicy Bypass -File resynth_benchmarks.ps1
```

### 2. 优化时钟周期
```powershell
powershell -ExecutionPolicy Bypass -File quick_optimize.ps1
```

### 3. 运行 OpenTimer 分析
```bash
cd /mnt/d/opentimer/OpenTimer
./bin/ot-shell < test_aes.tcl
```

## 依赖

- OpenTimer 2.1.0
- Yosys (用于综合)
- SAED32 RVT 标准单元库

## 许可证

- OpenTimer: 见 OpenTimer/LICENSE
- SAED32 库: 见相应许可证文件

