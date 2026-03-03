#!/usr/bin/env python3
"""检查 backup 文件中的重复边"""
import json
from pathlib import Path
from collections import Counter, defaultdict

backup = Path("D:/bishe_database/benchmark/test_output/gcd/anchor_corners/tt0p85v25c/train/arc_delay.json.backup")

print("=" * 60)
print("Checking Duplicates in backup")
print("=" * 60)

with open(backup, 'r', encoding='utf-8') as f:
    data = json.load(f)

arcs = data.get('arcs', [])
print(f"\nTotal arcs: {len(arcs)}")

# 按 (src, dst, edge_type) 分组
groups = defaultdict(list)
for arc in arcs:
    key = (arc['src'], arc['dst'], arc['edge_type'])
    groups[key].append(arc)

print(f"Unique (src, dst, edge_type): {len(groups)}")

# 找出重复的
duplicates = {k: v for k, v in groups.items() if len(v) > 1}
print(f"Duplicate groups: {len(duplicates)}")

if duplicates:
    print(f"\nSample duplicate groups (first 5):")
    for i, (key, arcs_list) in enumerate(list(duplicates.items())[:5]):
        print(f"\n  Group {i+1}: {key}")
        print(f"    Count: {len(arcs_list)}")
        for arc in arcs_list:
            edge_id = arc['edge_id']
            delay = arc.get('delay', {})
            mask = arc.get('mask', {})
            has_value = any(
                mask.get(f'mask{ch}', 0) == 1 and abs(delay.get(f'd{ch}', 0)) > 1e-12
                for ch in ['RR', 'RF', 'FR', 'FF']
            )
            print(f"      edge_id={edge_id}, has_value={has_value}")

print("\n" + "=" * 60)






















