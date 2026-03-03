#!/usr/bin/env python3
"""验证 graph_edges.csv 的 edge_id 是否连续"""
import csv
from pathlib import Path

graph_edges_file = Path("D:/bishe_database/benchmark/test_output/gcd/static/graph_edges.csv")

print("=" * 60)
print("Verifying Canonical Edge ID")
print("=" * 60)

with open(graph_edges_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    edges = list(reader)

edge_ids = [int(e['edge_id']) for e in edges]

print(f"\nTotal edges: {len(edges)}")
print(f"Edge_id range: {min(edge_ids)} - {max(edge_ids)}")
print(f"Unique edge_ids: {len(set(edge_ids))}")
print(f"Is continuous (0 to N-1): {set(edge_ids) == set(range(len(edges)))}")

if set(edge_ids) == set(range(len(edges))):
    print("\n[OK] Edge_id is continuous and canonical (0-1400)")
else:
    print("\n[ERROR] Edge_id is not continuous!")
    missing = set(range(len(edges))) - set(edge_ids)
    extra = set(edge_ids) - set(range(len(edges)))
    if missing:
        print(f"  Missing edge_ids: {sorted(list(missing))[:10]}")
    if extra:
        print(f"  Extra edge_ids: {sorted(list(extra))[:10]}")

print(f"\nFirst 3 edges:")
for e in edges[:3]:
    print(f"  edge_id={e['edge_id']}, {e['src']} -> {e['dst']}, type={e['edge_type']}")

print(f"\nLast 3 edges:")
for e in edges[-3:]:
    print(f"  edge_id={e['edge_id']}, {e['src']} -> {e['dst']}, type={e['edge_type']}")

print("\n" + "=" * 60)






















