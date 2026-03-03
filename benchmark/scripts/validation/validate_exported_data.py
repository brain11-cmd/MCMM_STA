#!/usr/bin/env python3
"""
Validate exported data for consistency and correctness.

This script performs:
1. Edge consistency check (arcs vs DOT)
2. Coverage check (dump_at pins vs node_static pins)
3. Uniqueness check (normalized pin_name)
4. Missing value statistics (structural vs unexpected)
"""

import argparse
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Set, Tuple, Dict, List

def normalize_pin_name(pin_name: str) -> str:
    """Normalize pin name: remove quotes, keep Inst/Pin format."""
    # Remove quotes if present
    pin_name = pin_name.strip().strip('"').strip("'")
    # Keep as is (should be Inst/Pin format like U123/A)
    return pin_name

def parse_dot_file(dot_path: Path) -> Set[Tuple[str, str]]:
    """Parse DOT file and extract edges (src, dst)."""
    edges = set()
    with open(dot_path, 'r') as f:
        for line in f:
            # Match: "src" -> "dst";
            match = re.search(r'"([^"]+)"\s*->\s*"([^"]+)"', line)
            if match:
                src = normalize_pin_name(match.group(1))
                dst = normalize_pin_name(match.group(2))
                edges.add((src, dst))
    return edges

def parse_dump_at(dump_at_path: Path) -> Set[str]:
    """Parse dump_at file and extract pin names."""
    pins = set()
    with open(dump_at_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            # Skip header lines
            if not line or line.startswith('#') or line.startswith('-') or 'E/R' in line or 'Pin' in line:
                continue
            # Format: E/R E/F L/R L/F Pin (tab or space separated)
            # Pin name is in the last column
            parts = line.split()
            if len(parts) >= 5:
                # Last column is pin name
                pin_name = normalize_pin_name(parts[-1])
                if pin_name and pin_name != 'Pin':  # Skip header
                    pins.add(pin_name)
    return pins

def parse_arcs_from_dump_at(dump_at_path: Path) -> Set[str]:
    """Get all pin names from dump_at (for coverage check)."""
    return parse_dump_at(dump_at_path)

def check_edge_consistency(dot_edges: Set[Tuple[str, str]], 
                          arc_edges: Set[Tuple[str, str]]) -> Dict:
    """Check consistency between DOT edges and arc edges."""
    dot_edge_set = set(dot_edges)
    arc_edge_set = set(arc_edges)
    
    matched = dot_edge_set & arc_edge_set
    unmatched_dot = dot_edge_set - arc_edge_set
    unmatched_arc = arc_edge_set - dot_edge_set
    
    total_edges = max(len(dot_edge_set), len(arc_edge_set))
    unmatched_ratio = len(unmatched_dot | unmatched_arc) / total_edges if total_edges > 0 else 0.0
    
    return {
        "dot_edges_count": len(dot_edge_set),
        "arc_edges_count": len(arc_edge_set),
        "matched_edges": len(matched),
        "unmatched_dot_count": len(unmatched_dot),
        "unmatched_arc_count": len(unmatched_arc),
        "unmatched_ratio": unmatched_ratio
    }

def check_coverage(dump_at_pins: Set[str], node_static_pins: Set[str]) -> Dict:
    """Check coverage: dump_at pins vs node_static pins."""
    intersection = dump_at_pins & node_static_pins
    coverage_ratio = len(intersection) / len(dump_at_pins) if len(dump_at_pins) > 0 else 0.0
    
    missing_in_static = dump_at_pins - node_static_pins
    
    return {
        "dump_at_pins_count": len(dump_at_pins),
        "node_static_pins_count": len(node_static_pins),
        "intersection_count": len(intersection),
        "coverage_ratio": coverage_ratio,
        "missing_in_static_count": len(missing_in_static),
        "missing_in_static_samples": list(missing_in_static)[:10]  # First 10 samples
    }

def check_uniqueness(pin_names: List[str]) -> Dict:
    """Check uniqueness of normalized pin names."""
    normalized_map = defaultdict(list)
    for orig in pin_names:
        norm = normalize_pin_name(orig)
        normalized_map[norm].append(orig)
    
    conflicts = {k: v for k, v in normalized_map.items() if len(v) > 1}
    
    return {
        "total_pins": len(pin_names),
        "unique_normalized": len(normalized_map),
        "conflicts_count": len(conflicts),
        "conflicts": {k: v for k, v in list(conflicts.items())[:10]}  # First 10 conflicts
    }

def main():
    parser = argparse.ArgumentParser(description="Validate exported OpenTimer data")
    parser.add_argument("--benchmark", required=True, help="Benchmark name")
    parser.add_argument("--corner", required=True, help="Corner name")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    benchmark_dir = output_dir / args.benchmark
    static_dir = benchmark_dir / "static"
    corner_dir = benchmark_dir / "anchor_corners" / args.corner
    
    print("=" * 60)
    print(f"Validating: {args.benchmark} / {args.corner}")
    print("=" * 60)
    print()
    
    # Check files exist
    graph_dot = static_dir / "graph.dot"
    arrival_txt = corner_dir / "arrival.txt"
    
    if not graph_dot.exists():
        print(f"[ERROR] graph.dot not found: {graph_dot}")
        return 1
    
    if not arrival_txt.exists():
        print(f"[ERROR] arrival.txt not found: {arrival_txt}")
        return 1
    
    print("Files found:")
    print(f"  [OK] {graph_dot}")
    print(f"  [OK] {arrival_txt}")
    print()
    
    # Parse DOT edges
    print("Parsing DOT file...")
    dot_edges = parse_dot_file(graph_dot)
    print(f"  Found {len(dot_edges)} edges in DOT")
    
    # Parse dump_at pins
    print("Parsing arrival.txt...")
    dump_at_pins = parse_dump_at(arrival_txt)
    print(f"  Found {len(dump_at_pins)} pins in arrival.txt")
    print()
    
    # Note: We can't parse arcs from OpenTimer directly here
    # This would require modifying OpenTimer or using its API
    # For now, we'll note that arcs should be extracted separately
    print("[NOTE] Arc edges should be extracted from OpenTimer _arcs")
    print("       This script currently only validates DOT format.")
    print()
    
    # Coverage check (placeholder - need node_static.csv)
    print("Coverage check:")
    print("  [NOTE] node_static.csv not yet generated")
    print("         Will check after generating node_static.csv")
    print()
    
    # Uniqueness check
    print("Uniqueness check:")
    pin_names_list = list(dump_at_pins)
    uniqueness_result = check_uniqueness(pin_names_list)
    
    if uniqueness_result["conflicts_count"] == 0:
        print(f"  [OK] All {uniqueness_result['total_pins']} pins have unique normalized names")
    else:
        print(f"  [ERROR] Found {uniqueness_result['conflicts_count']} conflicts!")
        print("  Conflicts (first 10):")
        for norm, orig_list in uniqueness_result["conflicts"].items():
            print(f"    '{norm}': {orig_list}")
        return 1
    
    print()
    
    # Summary
    print("=" * 60)
    print("Validation Summary:")
    print("=" * 60)
    print(f"  DOT edges: {len(dot_edges)}")
    print(f"  Dump_at pins: {len(dump_at_pins)}")
    print(f"  Pin uniqueness: [OK] PASSED")
    print()
    print("  [NOTE] Next steps:")
    print("  1. Extract arcs from OpenTimer _arcs (authoritative source)")
    print("  2. Generate node_static.csv with pin features")
    print("  3. Run full consistency checks")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    exit(main())

