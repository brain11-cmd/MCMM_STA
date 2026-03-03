#!/usr/bin/env python3
"""Generate arc_delay.json from graph.dot (placeholder - needs OpenTimer dump_arc_delay).

This is a temporary solution until we add dump_arc_delay to OpenTimer.
For now, we'll create a structure that can be filled in later.
"""
import json
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple

def parse_graph_edges(dot_file: Path) -> List[Tuple[str, str]]:
    """Parse graph.dot to extract edges."""
    edges = []
    
    with open(dot_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if '->' in line:
                match = re.match(r'"([^"]+)"\s*->\s*"([^"]+)"', line)
                if match:
                    src, dst = match.groups()
                    edges.append((src, dst))
    
    return edges

def determine_edge_type(src: str, dst: str) -> int:
    """Determine edge type: 0=cell_arc, 1=net_arc.
    
    This is a heuristic - in real implementation, we'd query OpenTimer.
    For now, we'll use a simple rule:
    - If src and dst have the same cell instance prefix, it's likely a cell_arc
    - Otherwise, it's likely a net_arc
    """
    # Extract cell instance from pin names
    # Format: "_387_:CLK" -> "_387_"
    def get_cell_instance(pin_name: str) -> str:
        if ':' in pin_name:
            return pin_name.rsplit(':', 1)[0]
        return pin_name
    
    src_cell = get_cell_instance(src)
    dst_cell = get_cell_instance(dst)
    
    # If same cell, likely cell_arc
    if src_cell == dst_cell:
        return 0  # cell_arc
    else:
        return 1  # net_arc

def generate_arc_delay_placeholder(
    dot_file: Path,
    output_file: Path,
    corner: str
):
    """Generate arc_delay.json placeholder structure."""
    
    print(f"Parsing graph.dot: {dot_file}")
    edges = parse_graph_edges(dot_file)
    print(f"  Found {len(edges)} edges")
    
    # Create arc_delay structure
    arc_delay_data = {
        "corner": corner,
        "time_unit": "ns",
        "arcs": []
    }
    
    print(f"\nGenerating arc_delay.json: {output_file}")
    print("  [NOTE] This is a placeholder - delay values need to be filled from OpenTimer")
    
    for edge_id, (src, dst) in enumerate(edges):
        edge_type = determine_edge_type(src, dst)
        
        # Placeholder delay values (all 0 with mask=0)
        # In real implementation, these should come from OpenTimer's _arcs
        arc_data = {
            "edge_id": edge_id,
            "src": src,
            "dst": dst,
            "edge_type": edge_type,
            "delay": {
                "dRR": 0.0,  # MAX, RISE, RISE
                "dRF": 0.0,  # MAX, RISE, FALL
                "dFR": 0.0,  # MAX, FALL, RISE
                "dFF": 0.0   # MAX, FALL, FALL
            },
            "mask": {
                "maskRR": 0,  # 1 if valid, 0 if missing
                "maskRF": 0,
                "maskFR": 0,
                "maskFF": 0
            }
        }
        
        # For net_arc, only RR and FF are valid
        if edge_type == 1:  # net_arc
            # Placeholder: mark RR and FF as potentially valid (but we don't have values)
            arc_data["mask"]["maskRR"] = 0  # Will be set to 1 when we have real data
            arc_data["mask"]["maskFF"] = 0  # Will be set to 1 when we have real data
        
        arc_delay_data["arcs"].append(arc_data)
    
    # Write JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(arc_delay_data, f, indent=2, ensure_ascii=False)
    
    print(f"  Generated {len(arc_delay_data['arcs'])} arc entries")
    print(f"\n  [WARNING] All delay values are placeholders (0.0)")
    print(f"  [WARNING] All masks are set to 0 (invalid)")
    print(f"  [WARNING] Need to implement dump_arc_delay in OpenTimer to get real values")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python generate_arc_delay_from_graph.py <graph.dot> <output.json> <corner>")
        sys.exit(1)
    
    dot_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    corner = sys.argv[3]
    
    if not dot_file.exists():
        print(f"Error: {dot_file} not found")
        sys.exit(1)
    
    generate_arc_delay_placeholder(dot_file, output_file, corner)


