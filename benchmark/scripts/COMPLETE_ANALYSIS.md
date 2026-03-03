# 完整脚本分析报告

## 📊 统计

- **总文件数**: 54 个
- **✅ 通用脚本**: 22 个 Python + 10 个 PowerShell = **32 个**
- **❌ 需要修改**: 11 个（7 个 Python + 4 个 PowerShell）
- **✅ 配置文件**: 3 个（通用）
- **📄 文档**: 1 个（示例用）

## ✅ 完全通用的脚本（可直接使用）

### Python 脚本（22 个）

1. **regenerate_graph_edges_canonical.py** ✅
2. **canonicalize_arc_delay_json.py** ✅
3. **generate_graph_edges_from_arc_delay.py** ✅
4. **generate_node_static_from_dump.py** ✅
5. **generate_node_static_from_pin_static.py** ✅
6. **validate_exported_data.py** ✅
7. **check_arc_arrival_correspondence.py** ✅
8. **analyze_arc_delay.py** ✅
9. **filter_instance_nodes.py** ✅
10. **generate_arc_delay_from_graph.py** ✅
11. **generate_node_static.py** ✅
12. **fix_na_cell_types.py** ✅
13. **analyze_arrival.py** ✅
14. **analyze_na_pins.py** ✅
15. **check_arc_delay_stats.py** ✅
16. **check_cell_types.py** ✅
17. **fix_gate_netlist.py** ✅
18. **过滤arc_delay.py** ✅
19. **export_arc_delay.tcl** ✅
20. **default.sdc** ✅
21. **ip_stubs.v** ✅

### PowerShell 脚本（10 个，有默认值但可覆盖）

1. **test_single_benchmark_data.ps1** ✅
2. **test_dump_timing_order.ps1** ✅
3. **test_timing_propagation.ps1** ✅
4. **cleanup_original_files.ps1** ✅
5. **verify_wns_tns_calculation.ps1** ✅
6. **optimize_worst_corner.ps1** ✅
7. **quick_optimize.ps1** ✅
8. **optimize_all_benchmarks.ps1** ✅
9. **prepare_opentimer.ps1** ✅
10. **fix_all_netlists.ps1** ✅

## ❌ 需要修改的脚本

### Python 脚本（7 个）

1. **compare_pin_cap_across_corners.py** ❌
   - 硬编码: `Path("D:/bishe_database/benchmark/test_output/gcd")`
   - 需要: 改为命令行参数

2. **verify_canonical_edge_id.py** ❌
   - 硬编码: `Path("D:/bishe_database/benchmark/test_output/gcd/static/graph_edges.csv")`
   - 需要: 改为命令行参数

3. **verify_arc_delay.py** ❌
   - 硬编码: `Path("D:/bishe_database/benchmark/test_output/gcd/anchor_corners/tt0p85v25c/train/arc_delay.json")`
   - 需要: 改为命令行参数

4. **compare_backup_files.py** ❌
   - 硬编码: `gcd` 和 `tt0p85v25c`
   - 需要: 改为命令行参数

5. **check_backup_duplicates.py** ❌
   - 硬编码: `gcd` 和 `tt0p85v25c`
   - 需要: 改为命令行参数

6. **check_edge_id_alignment.py** ❌
   - 硬编码: `gcd` 和 `tt0p85v25c`
   - 需要: 改为命令行参数

7. **check_node_edge_alignment.py** ❌
   - 硬编码: `gcd`
   - 需要: 改为命令行参数

### Python 脚本（部分硬编码 corner，但 benchmark 已参数化）

8. **unified_filter_pipeline.py** ⚠️
   - 硬编码: `tt0p85v25c`（第386行）
   - benchmark 已参数化
   - 需要: 添加 corner 参数或自动检测

9. **filter_instance_from_data.py** ⚠️
   - 硬编码: `tt0p85v25c`（第171行）
   - benchmark 已参数化
   - 需要: 添加 corner 参数或自动检测

10. **check_node_consistency.py** ⚠️
    - 硬编码: `tt0p85v25c`（第151行）
    - benchmark 已参数化
    - 需要: 添加 corner 参数或自动检测

11. **过滤instanace脚本.py** ⚠️
    - 硬编码: `tt0p85v25c`（第386行）
    - benchmark 已参数化
    - 需要: 添加 corner 参数或自动检测

### PowerShell 脚本（4 个）

1. **test_timing_simple.ps1** ❌
   - 硬编码: `gcd` 和 `tt0p85v25c`（第115行）
   - 虽然有参数，但第115行硬编码了路径
   - 需要: 修改第115行使用参数

2. **optimize_clock_period.ps1** ❌
   - 硬编码: `aes` benchmark（多处）
   - 需要: 添加 Benchmark 参数

3. **fix_all_benchmarks.ps1** ⚠️
   - 有默认路径，但应该可以通过参数覆盖
   - 需要检查

4. **fix_sdc_bom.ps1** ⚠️
   - 有默认路径，但应该可以通过参数覆盖
   - 需要检查

## 🔧 快速修复模板

### Python 脚本修复模板

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

# 对于需要 corner 的脚本
if len(sys.argv) >= 3:
    corner_name = sys.argv[2]
else:
    # 自动检测第一个 corner
    corners_dir = benchmark_dir / "anchor_corners"
    corners = list(corners_dir.iterdir())
    if not corners:
        print("Error: No corners found")
        sys.exit(1)
    corner_name = corners[0].name
    print(f"Using first corner: {corner_name}")

corner_dir = benchmark_dir / "anchor_corners" / corner_name
```

### PowerShell 脚本修复模板

```powershell
param(
    [string]$Benchmark = "gcd",  # 默认值
    [string]$Corner = "tt0p85v25c",  # 默认值
    [string]$OutputDir = "D:\bishe_database\benchmark\test_output"
)

# 原来: $arrivalFile = "D:\bishe_database\benchmark\test_output\gcd\anchor_corners\tt0p85v25c\arrival.txt"
# 改为:
$arrivalFile = Join-Path $OutputDir "$Benchmark\anchor_corners\$Corner\arrival.txt"
```

## 📋 优先级建议

### 高优先级（经常使用）

1. **unified_filter_pipeline.py** - 核心流水线脚本
2. **filter_instance_from_data.py** - 数据过滤脚本
3. **check_node_consistency.py** - 验证脚本

### 中优先级（验证脚本）

4. **verify_canonical_edge_id.py**
5. **verify_arc_delay.py**
6. **check_edge_id_alignment.py**
7. **check_node_edge_alignment.py**

### 低优先级（分析脚本）

8. **compare_pin_cap_across_corners.py**
9. **compare_backup_files.py**
10. **check_backup_duplicates.py**
11. **test_timing_simple.ps1**
12. **optimize_clock_period.ps1**

## ✅ 结论

- **32 个脚本**可以直接用于其他 benchmark/corner
- **11 个脚本**需要修改（主要是添加参数或修改硬编码路径）
- 大部分脚本已经参数化，只需要修复少数硬编码的地方






















