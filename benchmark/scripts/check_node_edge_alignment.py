#!/usr/bin/env python3
"""检查 node_static_train.csv 和 graph_edges.csv 的对齐关系"""
import csv
from pathlib import Path

node_file = Path("D:/bishe_database/benchmark/test_output/gcd/static/node_static_train.csv")
edge_file = Path("D:/bishe_database/benchmark/test_output/gcd/static/graph_edges.csv")

print("=" * 60)
print("Checking Node-Edge Alignment")
print("=" * 60)

# 读取 node_static_train.csv
print(f"\n[Step 1] Reading {node_file.name}...")
with open(node_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    nodes = list(reader)

node_pins = {node['pin_name'] for node in nodes}
print(f"  Total nodes: {len(nodes)}")
print(f"  Unique pin_names: {len(node_pins)}")

# 读取 graph_edges.csv
print(f"\n[Step 2] Reading {edge_file.name}...")
with open(edge_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    edges = list(reader)

edge_srcs = {edge['src'] for edge in edges}
edge_dsts = {edge['dst'] for edge in edges}
edge_pins = edge_srcs | edge_dsts

print(f"  Total edges: {len(edges)}")
print(f"  Unique src pins: {len(edge_srcs)}")
print(f"  Unique dst pins: {len(edge_dsts)}")
print(f"  Unique pins in edges: {len(edge_pins)}")

# 检查对齐
print(f"\n[Step 3] Checking alignment...")
pins_only_in_nodes = node_pins - edge_pins
pins_only_in_edges = edge_pins - node_pins
common_pins = node_pins & edge_pins

print(f"  Common pins: {len(common_pins)}")
print(f"  Pins only in node_static: {len(pins_only_in_nodes)}")
print(f"  Pins only in graph_edges: {len(pins_only_in_edges)}")

# 检查覆盖率
node_coverage = len(common_pins) / len(node_pins) * 100 if node_pins else 0
edge_coverage = len(common_pins) / len(edge_pins) * 100 if edge_pins else 0

print(f"\n[Step 4] Coverage:")
print(f"  Node coverage (pins in edges / pins in nodes): {edge_coverage:.2f}%")
print(f"  Edge coverage (pins in nodes / pins in edges): {node_coverage:.2f}%")

# 显示差异
if pins_only_in_nodes:
    print(f"\n[INFO] Pins only in node_static (first 10):")
    for pin in list(pins_only_in_nodes)[:10]:
        print(f"    {pin}")

if pins_only_in_edges:
    print(f"\n[WARNING] Pins only in graph_edges (first 10):")
    for pin in list(pins_only_in_edges)[:10]:
        print(f"    {pin}")

# 检查 edge 的 src/dst 是否都在 node_static 中
print(f"\n[Step 5] Edge validation:")
edges_with_missing_src = [e for e in edges if e['src'] not in node_pins]
edges_with_missing_dst = [e for e in edges if e['dst'] not in node_pins]

print(f"  Edges with src not in node_static: {len(edges_with_missing_src)}")
print(f"  Edges with dst not in node_static: {len(edges_with_missing_dst)}")

if edges_with_missing_src:
    print(f"  Sample edges with missing src (first 5):")
    for e in edges_with_missing_src[:5]:
        print(f"    edge_id={e['edge_id']}, src={e['src']}, dst={e['dst']}")

if edges_with_missing_dst:
    print(f"  Sample edges with missing dst (first 5):")
    for e in edges_with_missing_dst[:5]:
        print(f"    edge_id={e['edge_id']}, src={e['src']}, dst={e['dst']}")

# 总结
print("\n" + "=" * 60)
if len(pins_only_in_edges) == 0 and len(edges_with_missing_src) == 0 and len(edges_with_missing_dst) == 0:
    print("[OK] Perfect alignment! All edge pins are in node_static.")
else:
    print("[WARNING] Some misalignments found.")
print("=" * 60)






















