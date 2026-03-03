# 单 Benchmark 数据导出和验证测试指南

## 概述

本指南用于测试单个 benchmark 的数据导出和一致性验证，确保数据格式正确、一致性检查通过。

## 快速开始

### 1. 选择一个测试 Benchmark

建议从较小的 benchmark 开始：
- **推荐**: `gcd` (最小，快速测试)
- **备选**: `aes`, `fifo`, `uart` (中等大小)

### 2. 运行数据导出

```powershell
cd D:\bishe_database\benchmark
.\scripts\test_single_benchmark_data.ps1 -Benchmark gcd -Corner tt0p85v25c
```

**参数说明**:
- `-Benchmark`: benchmark 名称（如 `gcd`, `aes`）
- `-Corner`: corner 名称（建议先用 anchor corner，如 `tt0p85v25c`）
- `-OutputDir`: 输出目录（默认: `D:\bishe_database\benchmark\test_output`）

### 3. 验证导出的数据

```powershell
python scripts/validate_exported_data.py --benchmark gcd --corner tt0p85v25c --output-dir test_output
```

## 输出文件结构

```
test_output/
└── gcd/
    ├── static/
    │   └── graph.dot              # 图结构（DOT 格式，仅用于交叉校验）
    └── anchor_corners/
        └── tt0p85v25c/
            ├── arrival.txt        # Arrival time (L/R, L/F)
            ├── slew.txt           # Slew (L/R, L/F)
            ├── pin_cap.txt        # Pin capacitance
            └── net_load.txt       # Net load
```

## 验证检查项

### ✅ 当前可验证的项

1. **文件存在性检查**: 确保所有必需文件都已导出
2. **Pin 唯一性检查**: 规范化后的 pin_name 必须唯一
3. **DOT 格式解析**: 验证 DOT 文件格式正确

### ⚠️ 需要进一步开发的项

1. **边一致性检查**: 
   - 需要从 OpenTimer `_arcs` 提取权威边集合
   - 与 DOT 边进行对比
   - **实现方式**: 需要修改 OpenTimer 添加 `dump_arcs` 命令，或使用 C++ API

2. **覆盖率检查**:
   - 需要生成 `node_static.csv`
   - 对比 `dump_at` 的 pin 集合 vs `node_static` 的 pin 集合
   - **实现方式**: 需要遍历 OpenTimer pins，提取静态特征

3. **缺失值统计**:
   - 需要导出 `arc_delay` 数据
   - 区分 `missing_structural` (Net Arc RF/FR) 和 `missing_unexpected`
   - **实现方式**: 需要遍历 OpenTimer arcs，访问 `_delay` 成员

## 下一步开发任务

### Phase 1: 基础数据导出（当前阶段）

- [x] 使用 OpenTimer 现有命令导出基础数据
- [ ] 添加 `dump_arcs` 命令（或使用 C++ API 提取 arcs）
- [ ] 生成 `node_static.csv`（fanin, fanout, cell_type, pin_role）

### Phase 2: 增强数据导出

- [ ] 导出 `arc_delay.json`（4 通道 + mask）
- [ ] 实现缺失值分级统计
- [ ] 生成完整的 CSV 文件集（按推荐格式）

### Phase 3: 完整验证

- [ ] 边一致性检查（arcs vs DOT）
- [ ] 覆盖率检查（dump_at vs node_static）
- [ ] 缺失值统计和验证

## 示例输出

### 成功输出示例

```
============================================
Testing Benchmark: gcd
Corner: tt0p85v25c
============================================

Files:
  Library: D:\bishe_database\BUFLIB\lib_rvt\saed32rvt_tt0p85v25c.lib
  Netlist: D:\bishe_database\benchmark\netlists\gcd\gcd_netlist.v
  SDC: D:\bishe_database\benchmark\netlists\gcd\gcd.sdc
  Output: D:\bishe_database\benchmark\test_output\gcd\anchor_corners\tt0p85v25c

Running OpenTimer for data export...

============================================
✅ OpenTimer export completed!

WNS: -0.123 ns
TNS: -0.456 ns

Checking exported files...
  ✅ graph.dot: 1234 lines
  ✅ arrival.txt: 567 lines
  ✅ slew.txt: 567 lines
  ✅ pin_cap.txt: 567 lines
  ✅ net_load.txt: 234 lines

============================================
✅ Data export completed successfully!

Next step: Run validation script:
  python scripts/validate_exported_data.py --benchmark gcd --corner tt0p85v25c --output-dir test_output
============================================
```

### 验证输出示例

```
============================================================
Validating: gcd / tt0p85v25c
============================================================

Files found:
  ✅ graph.dot
  ✅ arrival.txt

Parsing DOT file...
  Found 1234 edges in DOT

Parsing arrival.txt...
  Found 567 pins in arrival.txt

⚠️  Note: Arc edges should be extracted from OpenTimer _arcs
   This script currently only validates DOT format.

Coverage check:
  ⚠️  node_static.csv not yet generated
  ⚠️  Will check after generating node_static.csv

Uniqueness check:
  ✅ All 567 pins have unique normalized names

============================================================
Validation Summary:
============================================================
  DOT edges: 1234
  Dump_at pins: 567
  Pin uniqueness: ✅ PASSED

⚠️  Next steps:
  1. Extract arcs from OpenTimer _arcs (authoritative source)
  2. Generate node_static.csv with pin features
  3. Run full consistency checks
============================================================
```

## 故障排除

### 问题 1: OpenTimer 无法加载网表

**症状**: 出现 ERROR 或 FATAL 错误

**解决方案**:
- 检查网表文件是否存在
- 检查库文件路径是否正确
- 检查 SDC 文件格式是否正确

### 问题 2: 导出的文件为空或缺失

**症状**: 文件存在但行数为 0

**解决方案**:
- 确保已运行 `update_timing`
- 检查 OpenTimer 输出是否有错误
- 检查是否有足够的 pin/arc 数据

### 问题 3: Pin 名称冲突

**症状**: 验证脚本报告 pin_name 冲突

**解决方案**:
- 检查 pin_name 规范化函数
- 查看冲突样本，定位问题
- 可能需要调整规范化规则

## 参考文档

- `模型输入方案.md`: 数据格式和导出要求
- `训练数据导出清单.md`: 完整文件列表
- `数据划分方案.md`: Corner 划分和 benchmark 列表


