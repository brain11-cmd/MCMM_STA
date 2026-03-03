#!/usr/bin/env python3
"""
整理 scripts 文件夹，将文件分类到不同文件夹，并删除重复/临时文件
"""
import shutil
from pathlib import Path

scripts_dir = Path(__file__).parent

# 文件夹映射
folder_mapping = {
    # 核心处理脚本
    'core': [
        'regenerate_graph_edges_canonical.py',
        'canonicalize_arc_delay_json.py',
        'generate_graph_edges_from_arc_delay.py',
        'unified_filter_pipeline.py',
    ],
    
    # 数据生成脚本
    'data_generation': [
        'generate_node_static_from_dump.py',
        'generate_node_static_from_pin_static.py',
        'generate_node_static.py',
        'generate_arc_delay_from_graph.py',
        'filter_instance_from_data.py',
    ],
    
    # 验证脚本
    'validation': [
        'check_edge_id_alignment.py',
        'check_node_edge_alignment.py',
        'check_node_consistency.py',
        'check_arc_arrival_correspondence.py',
        'validate_exported_data.py',
        'verify_arc_delay.py',
        'verify_canonical_edge_id.py',
    ],
    
    # 分析脚本
    'analysis': [
        'analyze_arc_delay.py',
        'analyze_arrival.py',
        'analyze_na_pins.py',
        'check_arc_delay_stats.py',
        'check_cell_types.py',
        'compare_pin_cap_across_corners.py',
    ],
    
    # 工具脚本
    'utilities': [
        'filter_instance_nodes.py',
        'fix_na_cell_types.py',
        'fix_gate_netlist.py',
        'cleanup_original_files.ps1',
        'cleanup_temp_files.ps1',
    ],
    
    # OpenTimer 相关
    'opentimer': [
        'test_single_benchmark_data.ps1',
        'test_dump_timing_order.ps1',
        'test_timing_propagation.ps1',
        'test_timing_simple.ps1',
        'test_chameleon_multicorner.ps1',
        'export_arc_delay.tcl',
        'check_timing_status.ps1',
    ],
    
    # 优化脚本
    'optimization': [
        'quick_optimize.ps1',
        'optimize_all_benchmarks.ps1',
        'optimize_worst_corner.ps1',
        'optimize_clock_period.ps1',
        'verify_wns_tns_calculation.ps1',
    ],
    
    # 综合脚本
    'synthesis': [
        'synth_saed32.tcl',
        'run_synth_all.ps1',
        'prepare_opentimer.ps1',
    ],
    
    # 维护脚本
    'maintenance': [
        'fix_all_benchmarks.ps1',
        'fix_all_netlists.ps1',
        'fix_sdc_bom.ps1',
    ],
    
    # 文档
    'docs': [
        'README_TEST_SINGLE_BENCHMARK.md',
        'COMPLETE_ANALYSIS.md',
        'GENERIC_SCRIPTS_REPORT.md',
        'QUICK_REFERENCE.md',
        'OTHER_FILES_ANALYSIS.md',
        'CLEANUP_PLAN.md',
    ],
    
    # 配置文件
    'config': [
        'default.sdc',
        'ip_stubs.v',
    ],
    
    # 已废弃的脚本（保留备份）
    'deprecated': [
        '过滤arc_delay.py',  # 旧版本，功能已被 canonicalize_arc_delay_json.py 替代
        '过滤instanace脚本.py',  # 旧版本，功能已被 unified_filter_pipeline.py 替代
        'compare_backup_files.py',  # 一次性分析工具
        'check_backup_duplicates.py',  # 一次性分析工具
    ],
}

# 要删除的文件（临时/分析输出）
files_to_delete = [
    'script_analysis.txt',  # 临时分析输出
    'analyze_script_generality.py',  # 一次性分析工具（已完成分析）
]

def create_folders():
    """创建所有需要的文件夹"""
    print("Creating folder structure...")
    for folder in folder_mapping.keys():
        folder_path = scripts_dir / folder
        folder_path.mkdir(exist_ok=True)
        print(f"  [OK] {folder}/")

def move_files():
    """移动文件到对应文件夹"""
    print("\nMoving files...")
    moved = 0
    not_found = []
    
    for folder, files in folder_mapping.items():
        for filename in files:
            src = scripts_dir / filename
            dst = scripts_dir / folder / filename
            
            if src.exists():
                if src != dst:  # 避免移动到自身
                    shutil.move(str(src), str(dst))
                    print(f"  [OK] {filename} -> {folder}/")
                    moved += 1
            else:
                not_found.append(filename)
    
    if not_found:
        print(f"\n⚠️  Files not found: {not_found}")
    
    print(f"\n[OK] Moved {moved} files")

def delete_files():
    """删除临时文件"""
    print("\nDeleting temporary files...")
    deleted = 0
    
    for filename in files_to_delete:
        file_path = scripts_dir / filename
        if file_path.exists():
            file_path.unlink()
            print(f"  [OK] Deleted {filename}")
            deleted += 1
        else:
            print(f"  - {filename} not found (already deleted?)")
    
    print(f"\n[OK] Deleted {deleted} files")

def create_readme():
    """创建 README 说明文件结构"""
    readme_content = """# Scripts Directory Structure

## 📁 Folder Organization

- **core/**: Core processing scripts (graph edges, arc delay canonicalization)
- **data_generation/**: Scripts for generating static data files
- **validation/**: Scripts for validating data consistency
- **analysis/**: Scripts for analyzing data patterns
- **utilities/**: Utility scripts for fixing/cleaning data
- **opentimer/**: OpenTimer-related test and export scripts
- **optimization/**: Optimization scripts
- **synthesis/**: Synthesis scripts
- **maintenance/**: Maintenance scripts for batch operations
- **docs/**: Documentation and analysis reports
- **config/**: Configuration files (SDC, Verilog stubs)
- **deprecated/**: Old/obsolete scripts (kept for reference)

## 🚀 Quick Start

### Core Workflow
1. `core/unified_filter_pipeline.py` - Main data processing pipeline
2. `core/regenerate_graph_edges_canonical.py` - Generate canonical graph edges
3. `core/canonicalize_arc_delay_json.py` - Canonicalize arc delay data

### Validation
- `validation/check_edge_id_alignment.py` - Check edge_id alignment
- `validation/validate_exported_data.py` - Validate exported data

## 📝 Notes

- Scripts in `deprecated/` are kept for reference but should not be used
- Most scripts accept command-line arguments - check individual scripts for usage
- See `docs/QUICK_REFERENCE.md` for detailed usage information
"""
    
    readme_path = scripts_dir / 'README.md'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"\n[OK] Created README.md")

def preview():
    """预览将要执行的操作"""
    print("=" * 60)
    print("Preview: Files to be organized")
    print("=" * 60)
    
    for folder, files in folder_mapping.items():
        existing = [f for f in files if (scripts_dir / f).exists()]
        if existing:
            print(f"\n{folder}/ ({len(existing)} files):")
            for f in existing:
                print(f"  - {f}")
    
    print(f"\n\nFiles to delete ({len(files_to_delete)}):")
    for f in files_to_delete:
        if (scripts_dir / f).exists():
            print(f"  - {f}")

def main():
    import sys
    
    # 检查是否有 --preview 参数
    if len(sys.argv) > 1 and sys.argv[1] == '--preview':
        preview()
        return
    
    # 检查是否有 --yes 参数（自动执行）
    auto_confirm = len(sys.argv) > 1 and sys.argv[1] == '--yes'
    
    print("=" * 60)
    print("Organizing Scripts Directory")
    print("=" * 60)
    
    if not auto_confirm:
        print("\n⚠️  This will reorganize files.")
        print("   Use --preview to see what will be done")
        print("   Use --yes to execute without confirmation")
        print("\nFor safety, run with --preview first!")
        return
    
    # 执行
    create_folders()
    move_files()
    delete_files()
    create_readme()
    
    print("\n" + "=" * 60)
    print("[OK] Organization complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review the new structure")
    print("2. Update any scripts that reference moved files")
    print("3. Test that everything still works")

if __name__ == "__main__":
    main()

