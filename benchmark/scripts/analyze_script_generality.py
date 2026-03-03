#!/usr/bin/env python3
"""
分析 scripts 文件夹中的所有脚本，判断哪些是通用的（可用于其他 benchmark/corner），
哪些是特定的（硬编码了路径或名称）
"""
import re
from pathlib import Path
from collections import defaultdict

scripts_dir = Path(__file__).parent

# 硬编码的路径模式
HARDCODED_PATTERNS = [
    r'D:[/\\]bishe_database',  # 绝对路径
    r'gcd',  # benchmark 名称
    r'tt0p85v25c',  # corner 名称
    r'test_output[/\\]gcd',  # 特定 benchmark 路径
]

# 通用参数模式（通过命令行参数或函数参数）
GENERIC_PATTERNS = [
    r'sys\.argv',
    r'argparse',
    r'Path\(sys\.argv',
    r'def.*\(.*Path.*\)',  # 函数接受 Path 参数
    r'benchmark.*=.*Path',  # 变量名包含 benchmark 且是 Path
    r'corner.*=.*Path',  # 变量名包含 corner 且是 Path
]

print("=" * 80)
print("Analyzing Script Generality")
print("=" * 80)

results = {
    'generic': [],  # 通用脚本
    'specific': [],  # 特定脚本（硬编码）
    'needs_review': [],  # 需要人工检查
}

# 分析每个 Python 脚本
current_file = Path(__file__).name
for script_file in sorted(scripts_dir.glob("*.py")):
    if script_file.name == current_file:
        continue
    
    print(f"\n{'='*80}")
    print(f"Analyzing: {script_file.name}")
    print(f"{'='*80}")
    
    with open(script_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查硬编码模式
    hardcoded_found = []
    for pattern in HARDCODED_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            hardcoded_found.append((pattern, len(matches)))
    
    # 检查通用模式
    generic_found = []
    for pattern in GENERIC_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            generic_found.append((pattern, len(matches)))
    
    # 判断
    if hardcoded_found and not generic_found:
        status = 'specific'
        print(f"  ❌ SPECIFIC: Contains hardcoded paths/names")
        for pattern, count in hardcoded_found:
            print(f"     - {pattern}: {count} occurrences")
    elif generic_found and not hardcoded_found:
        status = 'generic'
        print(f"  ✅ GENERIC: Uses parameters/arguments")
        for pattern, count in generic_found:
            print(f"     - {pattern}: {count} occurrences")
    elif hardcoded_found and generic_found:
        status = 'needs_review'
        print(f"  ⚠️  NEEDS REVIEW: Has both hardcoded and generic patterns")
        print(f"     Hardcoded: {[p[0] for p in hardcoded_found]}")
        print(f"     Generic: {[p[0] for p in generic_found]}")
    else:
        # 检查是否有明显的参数化
        if 'sys.argv' in content or 'argparse' in content:
            status = 'generic'
            print(f"  ✅ GENERIC: Uses command-line arguments")
        else:
            status = 'needs_review'
            print(f"  ⚠️  NEEDS REVIEW: No clear patterns found")
    
    results[status].append((script_file.name, hardcoded_found, generic_found))

# 总结
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

print(f"\n✅ GENERIC SCRIPTS ({len(results['generic'])}):")
for name, _, _ in results['generic']:
    print(f"   - {name}")

print(f"\n❌ SPECIFIC SCRIPTS ({len(results['specific'])}):")
for name, hardcoded, _ in results['specific']:
    print(f"   - {name}")
    if hardcoded:
        print(f"     Hardcoded: {[p[0] for p in hardcoded]}")

print(f"\n⚠️  NEEDS REVIEW ({len(results['needs_review'])}):")
for name, hardcoded, generic in results['needs_review']:
    print(f"   - {name}")
    if hardcoded:
        print(f"     Hardcoded: {[p[0] for p in hardcoded]}")
    if generic:
        print(f"     Generic: {[p[0] for p in generic]}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)
print("""
1. GENERIC scripts: Can be used for other benchmarks/corners as-is
2. SPECIFIC scripts: Need to modify hardcoded paths/names before use
3. NEEDS REVIEW: Check manually to determine if they're generic or specific
""")

