#!/usr/bin/env python3
"""
重新生成 graph_edges.csv，基于去重后的唯一边，edge_id 连续（0-1400）。

这是正确的做法：
1. graph_edges.csv 是权威边定义，应该基于去重后的唯一边
2. edge_id 应该是连续的 0, 1, 2, ..., N-1
3. arc_delay.json 的 edge_id 应该和 graph_edges.csv 对齐
"""

import json
import csv
import sys
from pathlib import Path
from collections import defaultdict

EPS = 1e-12


def normalize_pin_name(pin_name: str) -> str:
    return pin_name.strip()


def is_valid_pin_name(pin_name: str) -> bool:
    if not pin_name:
        return False
    if ':' in pin_name:
        parts = pin_name.split(':', 1)
        if len(parts) < 2 or not parts[1]:
            return False
    return True


def compute_valid_nonzero_count(arc: dict) -> int:
    delay = arc.get('delay', {})
    mask = arc.get('mask', {})
    count = 0
    if mask.get('maskRR', 0) == 1 and abs(delay.get('dRR', 0)) > EPS:
        count += 1
    if mask.get('maskRF', 0) == 1 and abs(delay.get('dRF', 0)) > EPS:
        count += 1
    if mask.get('maskFR', 0) == 1 and abs(delay.get('dFR', 0)) > EPS:
        count += 1
    if mask.get('maskFF', 0) == 1 and abs(delay.get('dFF', 0)) > EPS:
        count += 1
    return count


def compute_sum_delay(arc: dict) -> float:
    delay = arc.get('delay', {})
    mask = arc.get('mask', {})
    total = 0.0
    if mask.get('maskRR', 0) == 1:
        total += abs(delay.get('dRR', 0))
    if mask.get('maskRF', 0) == 1:
        total += abs(delay.get('dRF', 0))
    if mask.get('maskFR', 0) == 1:
        total += abs(delay.get('dFR', 0))
    if mask.get('maskFF', 0) == 1:
        total += abs(delay.get('dFF', 0))
    return total


def select_best_arc(candidates: list) -> dict:
    """选择最优 arc（规则 A/B）"""
    scored = []
    for arc in candidates:
        nonzero_count = compute_valid_nonzero_count(arc)
        sum_delay = compute_sum_delay(arc)
        scored.append({
            'arc': arc,
            'nonzero_count': nonzero_count,
            'sum_delay': sum_delay
        })
    
    scored.sort(key=lambda x: x['nonzero_count'], reverse=True)
    max_nonzero = scored[0]['nonzero_count']
    
    top_nonzero = [s for s in scored if s['nonzero_count'] == max_nonzero]
    top_nonzero.sort(key=lambda x: x['sum_delay'], reverse=True)
    
    return top_nonzero[0]['arc']


def regenerate_graph_edges(backup_file: Path, output_file: Path):
    """从 backup 文件重新生成 graph_edges.csv，应用去重规则"""
    print("=" * 60)
    print("Regenerating graph_edges.csv (Canonical Version)")
    print("=" * 60)
    
    # 读取 backup（原始文件）
    print(f"\n[Step 1] Reading {backup_file.name}...")
    with open(backup_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    raw_arcs = data.get('arcs', [])
    print(f"  Total arcs: {len(raw_arcs)}")
    
    # 过滤无效 pin
    print(f"\n[Step 2] Filtering invalid pins...")
    valid_arcs = []
    for arc in raw_arcs:
        src = normalize_pin_name(arc.get('src', ''))
        dst = normalize_pin_name(arc.get('dst', ''))
        if is_valid_pin_name(src) and is_valid_pin_name(dst):
            valid_arcs.append(arc)
    
    print(f"  Valid arcs: {len(valid_arcs)}")
    
    # 按 (src, dst, edge_type) 分组
    print(f"\n[Step 3] Grouping and selecting best arcs...")
    groups = defaultdict(list)
    for arc in valid_arcs:
        src = normalize_pin_name(arc.get('src', ''))
        dst = normalize_pin_name(arc.get('dst', ''))
        edge_type = arc.get('edge_type', 0)
        key = (src, dst, edge_type)
        groups[key].append(arc)
    
    # 对每组选择最优 arc
    selected_arcs = []
    for key, candidates in groups.items():
        if len(candidates) == 1:
            selected = candidates[0]
        else:
            selected = select_best_arc(candidates)
        selected_arcs.append((key, selected))
    
    print(f"  Selected arcs: {len(selected_arcs)}")
    
    # 生成 graph_edges.csv（edge_id 连续 0-1400）
    print(f"\n[Step 4] Generating {output_file.name}...")
    
    edges = []
    for idx, (key, arc) in enumerate(selected_arcs):
        src, dst, edge_type = key
        edges.append({
            'edge_id': idx,  # 连续 edge_id: 0, 1, 2, ...
            'src': src,
            'dst': dst,
            'edge_type': edge_type
        })
    
    # 按 edge_id 排序（应该已经是顺序的）
    edges.sort(key=lambda x: x['edge_id'])
    
    # 写入 CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['edge_id', 'src', 'dst', 'edge_type'])
        writer.writeheader()
        writer.writerows(edges)
    
    print(f"  Wrote {len(edges)} edges to {output_file.name}")
    print(f"  Edge_id range: 0 - {len(edges)-1} (continuous)")
    
    # 建立 key -> edge_id 映射
    key_to_edge_id = {}
    for edge in edges:
        key = (edge['src'], edge['dst'], edge['edge_type'])
        key_to_edge_id[key] = edge['edge_id']
    
    return key_to_edge_id


def update_arc_delay_edge_id(arc_delay_file: Path, key_to_edge_id: dict, output_file: Path):
    """更新 arc_delay.json 的 edge_id，使其与 graph_edges.csv 对齐"""
    print(f"\n[Step 5] Updating {arc_delay_file.name} edge_id...")
    
    with open(arc_delay_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    arcs = data.get('arcs', [])
    updated_count = 0
    missing_count = 0
    
    for arc in arcs:
        src = normalize_pin_name(arc.get('src', ''))
        dst = normalize_pin_name(arc.get('dst', ''))
        edge_type = arc.get('edge_type', 0)
        key = (src, dst, edge_type)
        
        if key in key_to_edge_id:
            new_edge_id = key_to_edge_id[key]
            if arc['edge_id'] != new_edge_id:
                arc['edge_id'] = new_edge_id
                updated_count += 1
        else:
            missing_count += 1
    
    # 按 edge_id 排序
    arcs.sort(key=lambda x: x['edge_id'])
    
    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"  Updated {updated_count} edge_ids")
    if missing_count > 0:
        print(f"  [WARNING] {missing_count} arcs not found in graph_edges.csv")
    print(f"  Wrote to {output_file.name}")


def main():
    if len(sys.argv) < 4:
        print("Usage: python regenerate_graph_edges_canonical.py <backup.json> <graph_edges.csv> <arc_delay.json>")
        sys.exit(1)
    
    backup_file = Path(sys.argv[1])
    graph_edges_file = Path(sys.argv[2])
    arc_delay_file = Path(sys.argv[3])
    
    if not backup_file.exists():
        print(f"Error: {backup_file} not found")
        sys.exit(1)
    
    # 重新生成 graph_edges.csv
    key_to_edge_id = regenerate_graph_edges(backup_file, graph_edges_file)
    
    # 更新 arc_delay.json 的 edge_id
    update_arc_delay_edge_id(arc_delay_file, key_to_edge_id, arc_delay_file)
    
    print("\n" + "=" * 60)
    print("[OK] graph_edges.csv regenerated with continuous edge_id (0-1400)")
    print("[OK] arc_delay.json edge_id updated to align with graph_edges.csv")
    print("=" * 60)


if __name__ == "__main__":
    main()

