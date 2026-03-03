#!/usr/bin/env python3
"""
从 arc_delay.json 生成 graph_edges.csv（权威边定义）。

根据方案，graph_edges.csv 是权威的边定义，arc_delay.json 的 edge_id 必须与其对齐。
"""

import json
import csv
import sys
from pathlib import Path


def generate_graph_edges(arc_delay_file: Path, output_file: Path):
    """从 arc_delay.json 生成 graph_edges.csv"""
    print("=" * 60)
    print("Generating graph_edges.csv from arc_delay.json")
    print("=" * 60)
    
    # 读取 arc_delay.json
    print(f"\n[Step 1] Reading {arc_delay_file.name}...")
    with open(arc_delay_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    arcs = data.get('arcs', [])
    print(f"  Total arcs: {len(arcs)}")
    
    # 生成 graph_edges.csv
    print(f"\n[Step 2] Generating {output_file.name}...")
    
    edges = []
    for arc in arcs:
        edges.append({
            'edge_id': arc['edge_id'],
            'src': arc['src'],
            'dst': arc['dst'],
            'edge_type': arc['edge_type']
        })
    
    # 按 edge_id 排序
    edges.sort(key=lambda x: x['edge_id'])
    
    # 写入 CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['edge_id', 'src', 'dst', 'edge_type'])
        writer.writeheader()
        writer.writerows(edges)
    
    print(f"  Wrote {len(edges)} edges to {output_file.name}")
    print(f"  Edge_id range: {edges[0]['edge_id']} - {edges[-1]['edge_id']}")
    
    # 验证
    edge_ids = [e['edge_id'] for e in edges]
    unique_edge_ids = len(set(edge_ids))
    print(f"\n[Step 3] Validation:")
    print(f"  Total edges: {len(edges)}")
    print(f"  Unique edge_ids: {unique_edge_ids}")
    print(f"  All edge_ids unique: {len(edges) == unique_edge_ids}")
    
    if len(edges) != unique_edge_ids:
        print(f"  [ERROR] Found duplicate edge_ids!")
        from collections import Counter
        dup = [eid for eid, count in Counter(edge_ids).items() if count > 1]
        print(f"  Duplicate edge_ids: {dup[:10]}")
    else:
        print(f"  [OK] All edge_ids are unique")
    
    # 检查 (src, dst, edge_type) 唯一性
    keys = [(e['src'], e['dst'], e['edge_type']) for e in edges]
    unique_keys = len(set(keys))
    print(f"  Unique (src, dst, edge_type): {unique_keys}")
    print(f"  All keys unique: {len(edges) == unique_keys}")
    
    if len(edges) != unique_keys:
        print(f"  [ERROR] Found duplicate (src, dst, edge_type)!")
    else:
        print(f"  [OK] All (src, dst, edge_type) are unique")
    
    print("\n" + "=" * 60)
    print("[OK] graph_edges.csv generated successfully!")
    print("=" * 60)
    
    return edges


def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_graph_edges_from_arc_delay.py <arc_delay.json> <graph_edges.csv>")
        sys.exit(1)
    
    arc_delay_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not arc_delay_file.exists():
        print(f"Error: {arc_delay_file} not found")
        sys.exit(1)
    
    generate_graph_edges(arc_delay_file, output_file)


if __name__ == "__main__":
    main()






















