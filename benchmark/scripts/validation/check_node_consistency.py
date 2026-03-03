#!/usr/bin/env python3
"""Check node consistency across all exported files."""
import json
import csv
import sys
from pathlib import Path
from collections import defaultdict

def load_train_nodes(csv_file: Path) -> set:
    """Load pin names from training node set."""
    pins = set()
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pins.add(row['pin_name'])
    return pins

def check_arc_delay_json(json_file: Path, train_nodes: set):
    """Check arc_delay.json for nodes not in train set."""
    print(f"\nChecking: {json_file.name}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    arcs = data.get('arcs', [])
    print(f"  Total arcs: {len(arcs)}")
    
    src_not_in_train = set()
    dst_not_in_train = set()
    edges_with_instance = []
    
    for arc in arcs:
        src = arc.get('src', '')
        dst = arc.get('dst', '')
        
        if src not in train_nodes:
            src_not_in_train.add(src)
            if src.endswith(':'):
                edges_with_instance.append((src, dst, 'src'))
        
        if dst not in train_nodes:
            dst_not_in_train.add(dst)
            if dst.endswith(':'):
                edges_with_instance.append((src, dst, 'dst'))
    
    print(f"  Arcs with src not in train set: {len(src_not_in_train)}")
    print(f"  Arcs with dst not in train set: {len(dst_not_in_train)}")
    
    if src_not_in_train:
        print(f"\n  Sample src nodes not in train (first 10):")
        for node in sorted(list(src_not_in_train))[:10]:
            print(f"    {node}")
    
    if dst_not_in_train:
        print(f"\n  Sample dst nodes not in train (first 10):")
        for node in sorted(list(dst_not_in_train))[:10]:
            print(f"    {node}")
    
    if edges_with_instance:
        print(f"\n  Edges involving __INSTANCE__ nodes (first 10):")
        for src, dst, which in edges_with_instance[:10]:
            print(f"    {which}: {src} -> {dst}")
    
    return len(src_not_in_train), len(dst_not_in_train), len(edges_with_instance)

def check_arrival_txt(txt_file: Path, train_nodes: set):
    """Check arrival.txt for nodes not in train set."""
    print(f"\nChecking: {txt_file.name}")
    
    pins_in_file = set()
    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('Arrival') or line.startswith('-') or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 5:
                pin_name = parts[-1]
                if pin_name.lower() not in ['pin', 'e/r', 'e/f', 'l/r', 'l/f']:
                    pins_in_file.add(pin_name)
    
    print(f"  Pins in file: {len(pins_in_file)}")
    
    not_in_train = pins_in_file - train_nodes
    if not_in_train:
        print(f"  Pins not in train set: {len(not_in_train)}")
        print(f"  Sample (first 10): {sorted(list(not_in_train))[:10]}")
    else:
        print(f"  [OK] All pins in train set")
    
    return len(not_in_train)

def check_graph_dot(dot_file: Path, train_nodes: set):
    """Check graph.dot for nodes not in train set."""
    print(f"\nChecking: {dot_file.name}")
    
    import re
    nodes_in_dot = set()
    edges_with_instance = []
    
    with open(dot_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('digraph') or line == '}':
                continue
            
            # Parse node
            if line.endswith(';') and '->' not in line:
                node = line.rstrip(';').strip().strip('"')
                if node:
                    nodes_in_dot.add(node)
            
            # Parse edge
            elif '->' in line:
                match = re.match(r'"([^"]+)"\s*->\s*"([^"]+)"', line)
                if match:
                    src, dst = match.groups()
                    nodes_in_dot.add(src)
                    nodes_in_dot.add(dst)
                    
                    if src.endswith(':') or dst.endswith(':'):
                        edges_with_instance.append((src, dst))
    
    print(f"  Nodes in DOT: {len(nodes_in_dot)}")
    
    not_in_train = nodes_in_dot - train_nodes
    if not_in_train:
        print(f"  Nodes not in train set: {len(not_in_train)}")
        instance_nodes = [n for n in not_in_train if n.endswith(':')]
        print(f"    __INSTANCE__ nodes: {len(instance_nodes)}")
        other_nodes = [n for n in not_in_train if not n.endswith(':')]
        if other_nodes:
            print(f"    Other nodes: {len(other_nodes)}")
            print(f"      Sample: {other_nodes[:5]}")
    
    if edges_with_instance:
        print(f"\n  Edges involving __INSTANCE__ nodes: {len(edges_with_instance)}")
        print(f"    Sample (first 5):")
        for src, dst in edges_with_instance[:5]:
            print(f"      {src} -> {dst}")
    
    return len(not_in_train), len(edges_with_instance)

def main():
    if len(sys.argv) < 2:
        print("Usage: python check_node_consistency.py <benchmark_dir>")
        print("  Example: python check_node_consistency.py test_output/gcd")
        sys.exit(1)
    
    benchmark_dir = Path(sys.argv[1])
    static_dir = benchmark_dir / "static"
    anchor_dir = benchmark_dir / "anchor_corners" / "tt0p85v25c"
    
    # Load training node set
    train_csv = static_dir / "node_static_train.csv"
    if not train_csv.exists():
        print(f"Error: {train_csv} not found")
        print("  Run filter_instance_nodes.py first")
        sys.exit(1)
    
    print(f"Loading training node set: {train_csv}")
    train_nodes = load_train_nodes(train_csv)
    print(f"  Training nodes: {len(train_nodes)}")
    
    # Check each file
    if (anchor_dir / "arc_delay.json").exists():
        check_arc_delay_json(anchor_dir / "arc_delay.json", train_nodes)
    
    if (anchor_dir / "arrival.txt").exists():
        check_arrival_txt(anchor_dir / "arrival.txt", train_nodes)
    
    if (static_dir / "graph.dot").exists():
        check_graph_dot(static_dir / "graph.dot", train_nodes)
    
    print("\n" + "="*60)
    print("Summary:")
    print("  Training node set should be the authoritative source")
    print("  Other files may contain __INSTANCE__ nodes (from DOT visualization)")
    print("  For training, filter edges that reference __INSTANCE__ nodes")

if __name__ == "__main__":
    main()


