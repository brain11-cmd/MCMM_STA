# 脚本整理方案

## 📁 建议的文件夹结构

```
scripts/
├── core/                    # 核心处理脚本
│   ├── regenerate_graph_edges_canonical.py
│   ├── canonicalize_arc_delay_json.py
│   ├── generate_graph_edges_from_arc_delay.py
│   └── unified_filter_pipeline.py
│
├── data_generation/         # 数据生成脚本
│   ├── generate_node_static_from_dump.py
│   ├── generate_node_static_from_pin_static.py
│   ├── generate_node_static.py
│   ├── generate_arc_delay_from_graph.py
│   └── filter_instance_from_data.py
│
├── validation/              # 验证脚本
│   ├── check_edge_id_alignment.py
│   ├── check_node_edge_alignment.py
│   ├── check_node_consistency.py
│   ├── check_arc_arrival_correspondence.py
│   ├── validate_exported_data.py
│   └── verify_arc_delay.py
│
├── analysis/                # 分析脚本
│   ├── analyze_arc_delay.py
│   ├── analyze_arrival.py
│   ├── analyze_na_pins.py
│   ├── check_arc_delay_stats.py
│   └── check_cell_types.py
│
├── utilities/               # 工具脚本
│   ├── filter_instance_nodes.py
│   ├── fix_na_cell_types.py
│   ├── fix_gate_netlist.py
│   └── cleanup_original_files.ps1
│
├── opentimer/              # OpenTimer 相关脚本
│   ├── test_single_benchmark_data.ps1
│   ├── test_dump_timing_order.ps1
│   ├── test_timing_propagation.ps1
│   ├── test_timing_simple.ps1
│   ├── test_chameleon_multicorner.ps1
│   ├── export_arc_delay.tcl
│   └── check_timing_status.ps1
│
├── optimization/            # 优化脚本
│   ├── quick_optimize.ps1
│   ├── optimize_all_benchmarks.ps1
│   ├── optimize_worst_corner.ps1
│   ├── optimize_clock_period.ps1
│   └── verify_wns_tns_calculation.ps1
│
├── synthesis/              # 综合脚本
│   ├── synth_saed32.tcl
│   ├── run_synth_all.ps1
│   └── prepare_opentimer.ps1
│
├── maintenance/            # 维护脚本
│   ├── fix_all_benchmarks.ps1
│   ├── fix_all_netlists.ps1
│   ├── fix_sdc_bom.ps1
│   └── cleanup_temp_files.ps1
│
├── docs/                   # 文档和分析报告
│   ├── README_TEST_SINGLE_BENCHMARK.md
│   ├── COMPLETE_ANALYSIS.md
│   ├── GENERIC_SCRIPTS_REPORT.md
│   ├── QUICK_REFERENCE.md
│   └── OTHER_FILES_ANALYSIS.md
│
├── config/                 # 配置文件
│   ├── default.sdc
│   └── ip_stubs.v
│
└── deprecated/             # 已废弃的脚本（保留备份）
    ├── 过滤arc_delay.py          # 旧版本，已被 canonicalize 替代
    └── 过滤instanace脚本.py      # 旧版本，已被 unified_filter_pipeline 替代
```

## 🗑️ 建议删除的文件

### 1. 临时/分析文件（可删除）
- `script_analysis.txt` - 临时分析输出
- `analyze_script_generality.py` - 一次性分析工具（已完成分析）

### 2. 重复/过时的脚本（移动到 deprecated/）

#### 高优先级（功能已被替代）
1. **过滤arc_delay.py** → 移动到 `deprecated/`
   - 功能：从 arc_delay.txt 生成 arc_delay.json
   - 替代：`canonicalize_arc_delay_json.py` 更完善
   - 但：如果还需要从 txt 转换，可以保留

2. **过滤instanace脚本.py** → 移动到 `deprecated/`
   - 功能：过滤 instance 节点
   - 替代：`unified_filter_pipeline.py` 更完善
   - 但：如果功能不完全相同，需要检查

#### 需要检查的脚本
3. **compare_backup_files.py** - 一次性分析工具，可删除或移动到 `docs/analysis/`
4. **check_backup_duplicates.py** - 一次性分析工具，可删除或移动到 `docs/analysis/`
5. **compare_pin_cap_across_corners.py** - 分析工具，可移动到 `analysis/` 或删除

### 3. 验证脚本（需要修复硬编码）

这些脚本需要修复后才能使用，建议：
- 修复后保留
- 或移动到 `validation/needs_fix/` 文件夹

## 📋 整理步骤

### Step 1: 创建文件夹结构
```powershell
cd D:\bishe_database\benchmark\scripts
mkdir core, data_generation, validation, analysis, utilities, opentimer, optimization, synthesis, maintenance, docs, config, deprecated
```

### Step 2: 移动文件到对应文件夹

### Step 3: 删除临时文件
- `script_analysis.txt`
- `analyze_script_generality.py` (可选，如果不再需要)

### Step 4: 检查重复功能
- 对比 `过滤arc_delay.py` 和 `canonicalize_arc_delay_json.py`
- 对比 `过滤instanace脚本.py` 和 `unified_filter_pipeline.py`

## ⚠️ 注意事项

1. **备份重要文件**：移动前先备份
2. **检查依赖**：确保没有其他脚本依赖这些文件
3. **更新路径**：如果有脚本引用这些文件，需要更新路径
4. **保留历史**：废弃的脚本移动到 `deprecated/` 而不是直接删除






















