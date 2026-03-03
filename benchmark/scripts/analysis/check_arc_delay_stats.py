#!/usr/bin/env python3
"""Check arc_delay.json statistics."""
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_arc_delay_stats.py <arc_delay.json>")
        sys.exit(1)
    
    json_file = Path(sys.argv[1])
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    arcs = data['arcs']
    cell_arcs = sum(1 for a in arcs if a['edge_type'] == 0)
    net_arcs = sum(1 for a in arcs if a['edge_type'] == 1)
    
    print(f"Arc Delay Statistics:")
    print(f"  Total arcs: {len(arcs)}")
    print(f"  Cell arcs: {cell_arcs} ({cell_arcs/len(arcs)*100:.1f}%)")
    print(f"  Net arcs: {net_arcs} ({net_arcs/len(arcs)*100:.1f}%)")
    print(f"  Corner: {data['corner']}")
    print(f"  Time unit: {data['time_unit']}")
    print(f"\n  [NOTE] All delay values are placeholders (0.0)")
    print(f"  [NOTE] Need to implement dump_arc_delay in OpenTimer")


