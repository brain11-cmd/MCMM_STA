#!/usr/bin/env python3
"""验证 arc_delay.json 是否还有重复边"""
import json
from collections import Counter
from pathlib import Path

json_file = Path("D:/bishe_database/benchmark/test_output/gcd/anchor_corners/tt0p85v25c/train/arc_delay.json")

with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

arcs = data['arcs']
print(f"Total arcs: {len(arcs)}")

# 检查重复
keys = [(a['src'], a['dst'], a['edge_type']) for a in arcs]
unique_keys = set(keys)
dup_counter = Counter(keys)
duplicates = [k for k, v in dup_counter.items() if v > 1]

print(f"Unique keys: {len(unique_keys)}")
print(f"Duplicate keys: {len(duplicates)}")

if duplicates:
    print("\nFirst 5 duplicates:")
    for dup in duplicates[:5]:
        count = dup_counter[dup]
        print(f"  {dup} appears {count} times")
        matching_arcs = [a for a in arcs if (a['src'], a['dst'], a['edge_type']) == dup]
        for arc in matching_arcs:
            print(f"    edge_id={arc['edge_id']}")
else:
    print("\n[OK] No duplicate edges found!")

# 显示最后几条
print(f"\nLast 3 arcs:")
for arc in arcs[-3:]:
    print(f"  edge_id={arc['edge_id']}, {arc['src']} -> {arc['dst']}, type={arc['edge_type']}")

