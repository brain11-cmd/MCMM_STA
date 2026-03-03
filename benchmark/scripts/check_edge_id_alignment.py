#!/usr/bin/env python3
"""检查 arc_delay.json 的 edge_id 是否正确对齐"""
import json
from pathlib import Path

json_file = Path("D:/bishe_database/benchmark/test_output/gcd/anchor_corners/tt0p85v25c/train/arc_delay.json")

with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

arcs = data['arcs']
edge_ids = [a['edge_id'] for a in arcs]

print(f"Total arcs: {len(arcs)}")
print(f"Edge_id range: {min(edge_ids)} - {max(edge_ids)}")
print(f"Unique edge_ids: {len(set(edge_ids))}")
print(f"All edge_ids unique: {len(edge_ids) == len(set(edge_ids))}")

# 检查是否有重复的 edge_id
from collections import Counter
dup_edge_ids = [eid for eid, count in Counter(edge_ids).items() if count > 1]
if dup_edge_ids:
    print(f"\n[ERROR] Found {len(dup_edge_ids)} duplicate edge_ids:")
    for eid in dup_edge_ids[:5]:
        matching = [a for a in arcs if a['edge_id'] == eid]
        print(f"  edge_id={eid}: {len(matching)} arcs")
        for arc in matching:
            print(f"    {arc['src']} -> {arc['dst']} (type={arc['edge_type']})")
else:
    print("\n[OK] No duplicate edge_ids")

# 检查是否有重复的 (src, dst, edge_type)
keys = [(a['src'], a['dst'], a['edge_type']) for a in arcs]
from collections import Counter
dup_keys = [k for k, count in Counter(keys).items() if count > 1]
if dup_keys:
    print(f"\n[ERROR] Found {len(dup_keys)} duplicate (src, dst, edge_type):")
    for key in dup_keys[:5]:
        matching = [a for a in arcs if (a['src'], a['dst'], a['edge_type']) == key]
        print(f"  {key}: {len(matching)} arcs with edge_ids: {[a['edge_id'] for a in matching]}")
else:
    print("\n[OK] No duplicate (src, dst, edge_type)")

print(f"\nFirst 3 arcs:")
for arc in arcs[:3]:
    print(f"  edge_id={arc['edge_id']}, {arc['src']} -> {arc['dst']}, type={arc['edge_type']}")

print(f"\nLast 3 arcs:")
for arc in arcs[-3:]:
    print(f"  edge_id={arc['edge_id']}, {arc['src']} -> {arc['dst']}, type={arc['edge_type']}")






















