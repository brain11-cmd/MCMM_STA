#!/usr/bin/env python3
"""
分析 validation 文件夹中的脚本，找出重复功能
"""
from pathlib import Path
import re

validation_dir = Path(__file__).parent

print("=" * 80)
print("Analyzing Validation Scripts")
print("=" * 80)

scripts_info = {}

current_file = Path(__file__).name
for script_file in sorted(validation_dir.glob("*.py")):
    if script_file.name == current_file:
        continue
    
    with open(script_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取功能描述
    docstring = ""
    if '"""' in content:
        parts = content.split('"""')
        if len(parts) >= 2:
            docstring = parts[1].strip().split('\n')[0]
    
    # 检查功能关键词
    content_lower = content.lower()
    keywords = {
        'edge_id': any(kw in content_lower for kw in ['edge_id', 'edge id', 'edgeid']),
        'duplicate': any(kw in content_lower for kw in ['duplicate', '重复']),
        'alignment': any(kw in content_lower for kw in ['alignment', '对齐']),
        'consistency': any(kw in content_lower for kw in ['consistency', '一致性']),
        'node': any(kw in content_lower for kw in ['node', '节点']),
        'arc_delay': any(kw in content_lower for kw in ['arc_delay', 'arc delay']),
        'graph_edges': any(kw in content_lower for kw in ['graph_edges', 'graph edges']),
        'arrival': 'arrival' in content_lower,
        'hardcoded': bool(re.search(r'gcd|tt0p85v25c|D:[/\\]bishe', content, re.IGNORECASE)),
    }
    
    # 检查参数化
    has_args = 'sys.argv' in content or 'argparse' in content
    
    scripts_info[script_file.name] = {
        'docstring': docstring,
        'keywords': keywords,
        'has_args': has_args,
        'size': len(content),
    }

# 打印分析结果
print("\nScript Analysis:")
print("-" * 80)

for name, info in scripts_info.items():
    print(f"\n{name}:")
    print(f"  Description: {info['docstring']}")
    print(f"  Keywords: {[k for k, v in info['keywords'].items() if v]}")
    print(f"  Has arguments: {info['has_args']}")
    print(f"  Hardcoded paths: {info['keywords']['hardcoded']}")
    print(f"  Size: {info['size']:,} bytes")

# 查找重复功能
print("\n" + "=" * 80)
print("Potential Duplicates:")
print("=" * 80)

# 按功能分组
groups = {
    'edge_id_check': [],
    'duplicate_check': [],
    'alignment_check': [],
    'consistency_check': [],
    'validation': [],
}

for name, info in scripts_info.items():
    if info['keywords']['edge_id']:
        groups['edge_id_check'].append(name)
    if info['keywords']['duplicate']:
        groups['duplicate_check'].append(name)
    if info['keywords']['alignment']:
        groups['alignment_check'].append(name)
    if info['keywords']['consistency']:
        groups['consistency_check'].append(name)
    if 'validate' in name.lower():
        groups['validation'].append(name)

for group_name, scripts in groups.items():
    if len(scripts) > 1:
        print(f"\n{group_name} ({len(scripts)} scripts):")
        for script in scripts:
            print(f"  - {script}")

# 建议
print("\n" + "=" * 80)
print("Recommendations:")
print("=" * 80)

duplicate_scripts = []
if len(groups['edge_id_check']) > 1:
    print(f"\n[DUPLICATE] Edge ID checking:")
    for script in groups['edge_id_check']:
        hardcoded = scripts_info[script]['keywords']['hardcoded']
        has_args = scripts_info[script]['has_args']
        status = "❌ Hardcoded" if hardcoded else ("✅ Parameterized" if has_args else "⚠️  No args")
        print(f"  - {script}: {status}")

if len(groups['duplicate_check']) > 1:
    print(f"\n[DUPLICATE] Duplicate checking:")
    for script in groups['duplicate_check']:
        hardcoded = scripts_info[script]['keywords']['hardcoded']
        has_args = scripts_info[script]['has_args']
        status = "❌ Hardcoded" if hardcoded else ("✅ Parameterized" if has_args else "⚠️  No args")
        print(f"  - {script}: {status}")

print("\n" + "=" * 80)

