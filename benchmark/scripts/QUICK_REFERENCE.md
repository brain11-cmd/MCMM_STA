# 脚本快速参考

## 🎯 核心通用脚本（推荐使用）

### 数据处理流程

1. **regenerate_graph_edges_canonical.py** - 重新生成规范的 graph_edges.csv
   ```bash
   python regenerate_graph_edges_canonical.py <backup.json> <graph_edges.csv> <arc_delay.json>
   ```

2. **canonicalize_arc_delay_json.py** - 规范化 arc_delay.json（去重）
   ```bash
   python canonicalize_arc_delay_json.py <arc_delay.json> [output.json]
   ```

3. **generate_graph_edges_from_arc_delay.py** - 从 arc_delay.json 生成 graph_edges.csv
   ```bash
   python generate_graph_edges_from_arc_delay.py <arc_delay.json> <graph_edges.csv>
   ```

4. **unified_filter_pipeline.py** - 统一过滤流水线
   ```bash
   python unified_filter_pipeline.py <benchmark_dir>
   ```

### 验证脚本

1. **check_edge_id_alignment.py** - 检查 edge_id 对齐（需要修改为参数）
2. **check_node_edge_alignment.py** - 检查节点和边对齐（需要修改为参数）
3. **verify_canonical_edge_id.py** - 验证 edge_id 连续性（需要修改为参数）

## ❌ 需要修改的脚本

这些脚本硬编码了 `gcd` 或 `tt0p85v25c`，需要改为参数：

1. **compare_pin_cap_across_corners.py** - 硬编码 `gcd`
2. **verify_canonical_edge_id.py** - 硬编码 `gcd`
3. **verify_arc_delay.py** - 硬编码 `gcd` 和 `tt0p85v25c`
4. **compare_backup_files.py** - 硬编码 `gcd` 和 `tt0p85v25c`
5. **check_backup_duplicates.py** - 硬编码 `gcd` 和 `tt0p85v25c`
6. **check_edge_id_alignment.py** - 硬编码 `gcd` 和 `tt0p85v25c`
7. **check_node_edge_alignment.py** - 硬编码 `gcd`

## 📝 修改建议

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

if len(sys.argv) >= 3:
    corner_name = sys.argv[2]
    corner_dir = benchmark_dir / "anchor_corners" / corner_name
else:
    # 如果没有指定 corner，处理所有 corner
    corner_dir = benchmark_dir / "anchor_corners"
```






















