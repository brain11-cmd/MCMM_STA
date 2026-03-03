# 其他文件分析报告

## PowerShell 脚本

### ✅ 通用脚本（有参数化）

1. **test_single_benchmark_data.ps1** ✅
   - 有默认值，但可以通过参数覆盖
   - 用法: `.\test_single_benchmark_data.ps1 -Benchmark <name> -Corner <corner>`
   - 参数: `-Benchmark`, `-Corner`, `-LibPath`, `-NetlistDir`, `-OutputDir`, `-OpenTimerPath`

2. **test_dump_timing_order.ps1** ⚠️
   - 有默认路径，需要检查参数化

3. **test_timing_propagation.ps1** ⚠️
   - 有默认路径，需要检查参数化

4. **test_timing_simple.ps1** ⚠️
   - 有默认路径，但第115行硬编码了 `gcd` 和 `tt0p85v25c`
   - 需要修改

5. **test_chameleon_multicorner.ps1** ⚠️
   - 有默认路径，需要检查参数化

6. **verify_wns_tns_calculation.ps1** ⚠️
   - 有默认路径，需要检查参数化

7. **quick_optimize.ps1** ⚠️
   - 有默认路径，需要检查参数化

8. **optimize_all_benchmarks.ps1** ⚠️
   - 有默认路径，需要检查参数化

9. **optimize_worst_corner.ps1** ⚠️
   - 有默认路径，需要检查参数化

10. **optimize_clock_period.ps1** ❌
    - 硬编码了 `aes` benchmark
    - 需要修改

11. **run_synth_all.ps1** ⚠️
    - 有默认路径，需要检查参数化

12. **check_timing_status.ps1** ⚠️
    - 有默认路径，需要检查参数化

13. **cleanup_original_files.ps1** ⚠️
    - 有默认路径，需要检查参数化

14. **cleanup_temp_files.ps1** ⚠️
    - 需要检查

15. **fix_all_benchmarks.ps1** ⚠️
    - 有默认路径，需要检查参数化

16. **fix_all_netlists.ps1** ⚠️
    - 有默认路径，需要检查参数化

17. **fix_sdc_bom.ps1** ⚠️
    - 有默认路径，需要检查参数化

18. **prepare_opentimer.ps1** ⚠️
    - 有默认路径，需要检查参数化

## Python 脚本（需要补充检查）

### ⚠️ 部分硬编码

1. **unified_filter_pipeline.py** ⚠️
   - 第386行硬编码了 `tt0p85v25c`
   - 需要改为参数或自动检测第一个 corner

2. **validate_exported_data.py** ✅
   - 使用 `argparse`，完全参数化
   - 用法: `python validate_exported_data.py --benchmark <name> --corner <corner> --output-dir <dir>`

3. **fix_gate_netlist.py** ✅
   - 使用 `argparse`，完全参数化

## TCL 脚本

1. **export_arc_delay.tcl** ✅
   - 通用脚本，无硬编码
   - 用于 OpenTimer 导出 arc_delay

2. **synth_saed32.tcl** ⚠️
   - 需要检查是否有硬编码

## 配置文件

1. **default.sdc** ✅
   - 通用 SDC 模板，无硬编码

2. **ip_stubs.v** ✅
   - 通用 Verilog stub 文件，无硬编码

## 文档文件

1. **README_TEST_SINGLE_BENCHMARK.md** ⚠️
   - 文档中有示例路径，但不影响脚本使用

## 总结

### 需要修改的文件（硬编码了 benchmark/corner）

#### Python 脚本
1. **unified_filter_pipeline.py** - 硬编码 `tt0p85v25c`（第386行）
2. **filter_instance_from_data.py** - 硬编码 `tt0p85v25c`（第171行）
3. **check_node_consistency.py** - 硬编码 `tt0p85v25c`（第151行）
4. **过滤instanace脚本.py** - 硬编码 `tt0p85v25c`（第386行）

#### PowerShell 脚本
1. **test_timing_simple.ps1** - 硬编码 `gcd` 和 `tt0p85v25c`（第115行）
2. **optimize_clock_period.ps1** - 硬编码 `aes` benchmark（第5-6行，第29行，第48-49行）

### 有默认值但可覆盖的文件（✅ 通用）

这些文件有默认值，但可以通过参数覆盖，所以是通用的：

1. **test_single_benchmark_data.ps1** ✅ - 默认 `gcd` 和 `tt0p85v25c`，但可通过参数覆盖
2. **test_dump_timing_order.ps1** ✅ - 默认 `gcd` 和 `tt0p85v25c`，但可通过参数覆盖
3. **test_timing_propagation.ps1** ✅ - 默认 `gcd` 和 `tt0p85v25c`，但可通过参数覆盖
4. **cleanup_original_files.ps1** ✅ - 默认 `gcd` 和 `tt0p85v25c`，但可通过参数覆盖
5. **verify_wns_tns_calculation.ps1** ✅ - 默认 `gcd`，但可通过参数覆盖
6. **optimize_worst_corner.ps1** ✅ - 默认 `gcd`，但可通过参数覆盖
7. **quick_optimize.ps1** ✅ - 包含多个 benchmark 列表，但可通过参数覆盖
8. **optimize_all_benchmarks.ps1** ✅ - 包含多个 benchmark 列表，但可通过参数覆盖
9. **prepare_opentimer.ps1** ✅ - 包含多个 benchmark 列表，但可通过参数覆盖
10. **fix_all_netlists.ps1** ✅ - 包含多个 benchmark 列表，但可通过参数覆盖

### 建议修改

#### unified_filter_pipeline.py
```python
# 原来: anchor_dir = benchmark_dir / "anchor_corners" / "tt0p85v25c"
# 改为:
anchor_corners_dir = benchmark_dir / "anchor_corners"
if len(sys.argv) >= 3:
    corner_name = sys.argv[2]
else:
    # 自动检测第一个 corner
    corners = list(anchor_corners_dir.iterdir())
    if not corners:
        print("Error: No corners found")
        sys.exit(1)
    corner_name = corners[0].name
    print(f"Using first corner: {corner_name}")

anchor_dir = anchor_corners_dir / corner_name
```

#### test_timing_simple.ps1
```powershell
# 原来: $arrivalFile = "D:\bishe_database\benchmark\test_output\gcd\anchor_corners\tt0p85v25c\arrival.txt"
# 改为: 使用参数或变量
$arrivalFile = Join-Path $OutputDir "$Benchmark\anchor_corners\$Corner\arrival.txt"
```

#### optimize_clock_period.ps1
```powershell
# 原来: [string]$NetlistPath = "D:\bishe_database\benchmark\netlists\aes\aes_netlist.v"
# 改为: 添加 Benchmark 参数
param(
    [string]$Benchmark = "aes",
    ...
)
$NetlistPath = Join-Path $NetlistDir "$Benchmark\${Benchmark}_netlist.v"
```

