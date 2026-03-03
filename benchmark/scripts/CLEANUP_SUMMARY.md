# 脚本整理总结

## 🗑️ 建议删除的文件

### 1. 临时/分析输出文件（可安全删除）
- ✅ `script_analysis.txt` - 临时分析输出
- ✅ `analyze_script_generality.py` - 一次性分析工具（已完成分析）

### 2. 重复/过时的脚本（移动到 deprecated/）

#### 已确认重复
1. **过滤instanace脚本.py** → `deprecated/`
   - 功能：统一过滤流水线
   - 替代：`unified_filter_pipeline.py`（功能更完善）
   - 状态：完全重复，可以废弃

2. **过滤arc_delay.py** → `deprecated/` 或保留
   - 功能：从 arc_delay.txt 生成 arc_delay.json
   - 替代：`canonicalize_arc_delay_json.py`（处理 json 文件）
   - 状态：输入不同（txt vs json），如果还需要从 txt 转换，可以保留
   - 建议：如果不再需要从 txt 转换，可以移动到 deprecated

#### 一次性分析工具（可删除或移动到 docs/analysis/）
3. **compare_backup_files.py** → `deprecated/` 或 `docs/analysis/`
   - 功能：比较备份文件
   - 状态：一次性分析工具，已完成任务

4. **check_backup_duplicates.py** → `deprecated/` 或 `docs/analysis/`
   - 功能：检查备份文件中的重复
   - 状态：一次性分析工具，已完成任务

## 📁 建议的文件夹结构

```
scripts/
├── core/                    # 核心处理脚本（4个）
│   ├── regenerate_graph_edges_canonical.py
│   ├── canonicalize_arc_delay_json.py
│   ├── generate_graph_edges_from_arc_delay.py
│   └── unified_filter_pipeline.py
│
├── data_generation/         # 数据生成脚本（5个）
│   ├── generate_node_static_from_dump.py
│   ├── generate_node_static_from_pin_static.py
│   ├── generate_node_static.py
│   ├── generate_arc_delay_from_graph.py
│   └── filter_instance_from_data.py
│
├── validation/              # 验证脚本（7个）
│   ├── check_edge_id_alignment.py
│   ├── check_node_edge_alignment.py
│   ├── check_node_consistency.py
│   ├── check_arc_arrival_correspondence.py
│   ├── validate_exported_data.py
│   ├── verify_arc_delay.py
│   └── verify_canonical_edge_id.py
│
├── analysis/                # 分析脚本（6个）
│   ├── analyze_arc_delay.py
│   ├── analyze_arrival.py
│   ├── analyze_na_pins.py
│   ├── check_arc_delay_stats.py
│   ├── check_cell_types.py
│   └── compare_pin_cap_across_corners.py
│
├── utilities/               # 工具脚本（5个）
│   ├── filter_instance_nodes.py
│   ├── fix_na_cell_types.py
│   ├── fix_gate_netlist.py
│   ├── cleanup_original_files.ps1
│   └── cleanup_temp_files.ps1
│
├── opentimer/              # OpenTimer 相关（7个）
│   ├── test_single_benchmark_data.ps1
│   ├── test_dump_timing_order.ps1
│   ├── test_timing_propagation.ps1
│   ├── test_timing_simple.ps1
│   ├── test_chameleon_multicorner.ps1
│   ├── export_arc_delay.tcl
│   └── check_timing_status.ps1
│
├── optimization/            # 优化脚本（5个）
│   ├── quick_optimize.ps1
│   ├── optimize_all_benchmarks.ps1
│   ├── optimize_worst_corner.ps1
│   ├── optimize_clock_period.ps1
│   └── verify_wns_tns_calculation.ps1
│
├── synthesis/              # 综合脚本（3个）
│   ├── synth_saed32.tcl
│   ├── run_synth_all.ps1
│   └── prepare_opentimer.ps1
│
├── maintenance/            # 维护脚本（3个）
│   ├── fix_all_benchmarks.ps1
│   ├── fix_all_netlists.ps1
│   └── fix_sdc_bom.ps1
│
├── docs/                   # 文档（6个）
│   ├── README_TEST_SINGLE_BENCHMARK.md
│   ├── COMPLETE_ANALYSIS.md
│   ├── GENERIC_SCRIPTS_REPORT.md
│   ├── QUICK_REFERENCE.md
│   ├── OTHER_FILES_ANALYSIS.md
│   └── CLEANUP_PLAN.md
│
├── config/                 # 配置文件（2个）
│   ├── default.sdc
│   └── ip_stubs.v
│
└── deprecated/             # 已废弃（4个）
    ├── 过滤arc_delay.py
    ├── 过滤instanace脚本.py
    ├── compare_backup_files.py
    └── check_backup_duplicates.py
```

## 📊 统计

- **总文件数**: 54 个
- **整理后**: 45 个活跃脚本 + 4 个废弃 + 6 个文档 = 55 个文件
- **删除**: 2 个临时文件
- **移动**: 49 个文件到分类文件夹

## ✅ 执行步骤

1. **运行整理脚本**：
   ```bash
   python organize_scripts.py
   ```

2. **检查结果**：确认文件都移动到正确位置

3. **更新引用**：如果有其他脚本引用这些文件，需要更新路径

4. **测试**：确保所有脚本仍然可以正常工作

## ⚠️ 注意事项

1. **备份**：执行前建议备份整个 scripts 文件夹
2. **依赖检查**：确保没有其他脚本硬编码了文件路径
3. **保留历史**：废弃的脚本移动到 `deprecated/` 而不是直接删除
4. **文档更新**：整理后更新相关文档中的路径引用






















