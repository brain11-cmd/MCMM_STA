# 通用脚本分析报告

## ✅ 通用脚本（可用于其他 benchmark/corner）

这些脚本通过命令行参数接受路径，不包含硬编码的 benchmark/corner 名称：

### Python 脚本（已验证通用）

1. **regenerate_graph_edges_canonical.py** ✅
   - 用法: `python regenerate_graph_edges_canonical.py <backup.json> <graph_edges.csv> <arc_delay.json>`

2. **canonicalize_arc_delay_json.py** ✅
   - 用法: `python canonicalize_arc_delay_json.py <arc_delay.json> [output.json]`

3. **generate_graph_edges_from_arc_delay.py** ✅
   - 用法: `python generate_graph_edges_from_arc_delay.py <arc_delay.json> <graph_edges.csv>`

4. **generate_node_static_from_dump.py** ✅
   - 用法: `python generate_node_static_from_dump.py <pin_static.txt> <arrival.txt> <output.csv>`

5. **generate_node_static_from_pin_static.py** ✅
   - 用法: `python generate_node_static_from_pin_static.py <pin_static.txt> <output.csv>`

6. **filter_instance_from_data.py** ✅
   - 用法: `python filter_instance_from_data.py <benchmark_dir>`

7. **unified_filter_pipeline.py** ✅
   - 用法: `python unified_filter_pipeline.py <benchmark_dir>`

8. **check_arc_arrival_correspondence.py** ✅
   - 用法: `python check_arc_arrival_correspondence.py <arrival.txt> <arc_delay.json> <arc_delay.txt>`

9. **analyze_arc_delay.py** ✅
   - 用法: `python analyze_arc_delay.py <arc_delay.json>`

10. **check_node_consistency.py** ✅
    - 用法: `python check_node_consistency.py <benchmark_dir>`

11. **fix_gate_netlist.py** ✅
    - 用法: 需要检查具体参数

12. **fix_na_cell_types.py** ✅
    - 用法: `python fix_na_cell_types.py <input.csv> <output.csv>`

13. **generate_arc_delay_from_graph.py** ✅
    - 用法: `python generate_arc_delay_from_graph.py <graph.dot> <output.json> <corner>`

14. **generate_node_static.py** ✅
    - 用法: `python generate_node_static.py <graph.dot> <arrival.txt> <output.csv>`

15. **filter_instance_nodes.py** ✅
    - 用法: `python filter_instance_nodes.py <input.csv> <output.csv>`

16. **analyze_arrival.py** ✅
    - 用法: `python analyze_arrival.py <arrival.txt>`

17. **analyze_na_pins.py** ✅
    - 用法: `python analyze_na_pins.py <node_static.csv>`

18. **check_arc_delay_stats.py** ✅
    - 用法: `python check_arc_delay_stats.py <arc_delay.json>`

19. **check_cell_types.py** ✅
    - 用法: `python check_cell_types.py <node_static.csv>`

20. **过滤arc_delay.py** ✅
    - 用法: `python 过滤arc_delay.py <arc_delay.txt> <output.json> [--edges <graph_edges.csv>] [--corner <corner>]`

21. **过滤instanace脚本.py** ✅
    - 用法: `python 过滤instanace脚本.py <benchmark_dir>`

22. **validate_exported_data.py** ✅
    - 用法: 需要检查具体参数

### PowerShell 脚本（部分通用）

1. **test_single_benchmark_data.ps1** ⚠️
   - 有默认路径，但可以通过参数覆盖
   - 用法: `.\test_single_benchmark_data.ps1 -Benchmark gcd -Corner tt0p85v25c`

2. **unified_filter_pipeline.py** ✅
   - Python 脚本，应该是通用的

## ❌ 特定脚本（需要修改硬编码路径）

这些脚本硬编码了 `gcd` 或 `tt0p85v25c`，需要修改后才能用于其他 benchmark/corner：

### Python 脚本

1. **compare_pin_cap_across_corners.py** ❌
   - 硬编码: `Path("D:/bishe_database/benchmark/test_output/gcd")`
   - 需要改为参数

2. **verify_canonical_edge_id.py** ❌
   - 硬编码: `Path("D:/bishe_database/benchmark/test_output/gcd/static/graph_edges.csv")`
   - 需要改为参数

3. **verify_arc_delay.py** ❌
   - 硬编码: `Path("D:/bishe_database/benchmark/test_output/gcd/anchor_corners/tt0p85v25c/train/arc_delay.json")`
   - 需要改为参数

4. **compare_backup_files.py** ❌
   - 硬编码: `gcd` 和 `tt0p85v25c`
   - 需要改为参数

5. **check_backup_duplicates.py** ❌
   - 硬编码: `gcd` 和 `tt0p85v25c`
   - 需要改为参数

6. **check_edge_id_alignment.py** ❌
   - 硬编码: `gcd` 和 `tt0p85v25c`
   - 需要改为参数

7. **check_node_edge_alignment.py** ❌
   - 硬编码: `gcd`
   - 需要改为参数

### PowerShell 脚本

大部分 PowerShell 脚本都有硬编码路径，但很多可以通过参数覆盖。

## ⚠️ PowerShell 脚本（部分通用）

大部分 PowerShell 脚本有默认路径，但可以通过参数覆盖：

1. **test_single_benchmark_data.ps1** ⚠️
   - 有默认路径，但可以通过 `-Benchmark` 和 `-Corner` 参数覆盖
   - 用法: `.\test_single_benchmark_data.ps1 -Benchmark <name> -Corner <corner>`

2. **其他 PowerShell 脚本** ⚠️
   - 大部分都有硬编码路径，需要修改或通过参数覆盖

## 📋 建议

### 对于通用脚本
- ✅ 可以直接用于其他 benchmark/corner
- ✅ 建议添加到文档中说明用法

### 对于特定脚本
- ❌ 需要修改硬编码路径为参数
- 🔧 建议重构为接受命令行参数

### 快速修复建议

对于硬编码的脚本，可以快速修改为：

```python
import sys
from pathlib import Path

# 原来: benchmark_dir = Path("D:/bishe_database/benchmark/test_output/gcd")
# 改为:
if len(sys.argv) < 2:
    print("Usage: python script.py <benchmark_name> [corner_name]")
    sys.exit(1)

benchmark_name = sys.argv[1]
benchmark_dir = Path(f"D:/bishe_database/benchmark/test_output/{benchmark_name}")
```

