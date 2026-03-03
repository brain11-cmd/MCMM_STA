#!/usr/bin/env python3
"""Generate node_static.csv from graph.dot and arrival.txt."""
import re
import sys
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, Tuple

def parse_graph_dot(dot_file: Path) -> Tuple[Set[str], Dict[str, Dict[str, int]]]:
    """Parse graph.dot to extract nodes and compute fanin/fanout."""
    nodes = set()
    fanin_count = defaultdict(int)
    fanout_count = defaultdict(int)
    
    with open(dot_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('digraph') or line == '}':
                continue
            
            # Parse node definition: "node_name";
            if line.endswith(';') and '->' not in line:
                node = line.rstrip(';').strip().strip('"')
                if node:
                    nodes.add(node)
            
            # Parse edge: "src" -> "dst";
            elif '->' in line:
                match = re.match(r'"([^"]+)"\s*->\s*"([^"]+)"', line)
                if match:
                    src, dst = match.groups()
                    fanout_count[src] += 1
                    fanin_count[dst] += 1
                    nodes.add(src)
                    nodes.add(dst)
    
    return nodes, {
        'fanin': dict(fanin_count),
        'fanout': dict(fanout_count)
    }

def parse_pin_name(pin_name: str) -> Tuple[str, str]:
    """Parse pin_name to extract cell_type and pin_role.
    
    Examples:
        "_387_:CLK" -> ("_387_", "CLK")
        "_385_:D" -> ("_385_", "D")
        "_349_:Y" -> ("_349_", "Y")
    """
    if ':' in pin_name:
        parts = pin_name.rsplit(':', 1)
        if len(parts) == 2:
            cell_name = parts[0]
            pin_role = parts[1]
            return cell_name, pin_role
    
    # Fallback: try to extract from common patterns
    # For now, return as-is
    return pin_name, "UNKNOWN"

def get_cell_type_from_pin(pin_name: str) -> str:
    """Extract cell type from pin name.
    
    For now, we'll use the cell instance name as a placeholder.
    In a full implementation, we'd need to query OpenTimer for the actual cell type.
    """
    cell_name, _ = parse_pin_name(pin_name)
    # This is a placeholder - in real implementation, query OpenTimer
    return cell_name

def generate_node_static(
    dot_file: Path,
    arrival_file: Path,
    output_file: Path
):
    """Generate node_static.csv from graph.dot and arrival.txt."""
    
    print(f"Parsing graph.dot: {dot_file}")
    nodes, counts = parse_graph_dot(dot_file)
    print(f"  Found {len(nodes)} nodes")
    print(f"  Nodes with fanin: {len(counts['fanin'])}")
    print(f"  Nodes with fanout: {len(counts['fanout'])}")
    
    # Get pins from arrival.txt (these are the pins with timing data)
    print(f"\nParsing arrival.txt: {arrival_file}")
    arrival_pins = set()
    with open(arrival_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('Arrival') or line.startswith('-') or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 5:
                pin_name = parts[-1]  # Last column is pin name
                # Skip header artifacts
                if pin_name.lower() in ['pin', 'e/r', 'e/f', 'l/r', 'l/f']:
                    continue
                arrival_pins.add(pin_name)
    
    print(f"  Found {len(arrival_pins)} pins in arrival.txt")
    
    # Use arrival_pins as the authoritative pin set
    # Add any nodes from graph.dot that aren't in arrival.txt
    all_pins = arrival_pins | nodes
    print(f"\nTotal unique pins: {len(all_pins)}")
    
    # Sort pins for stable node_id assignment
    sorted_pins = sorted(all_pins)
    
    # Generate node_static.csv
    print(f"\nGenerating node_static.csv: {output_file}")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['node_id', 'pin_name', 'fanin', 'fanout', 'cell_type', 'pin_role'])
        
        for node_id, pin_name in enumerate(sorted_pins, start=0):
            cell_name, pin_role = parse_pin_name(pin_name)
            cell_type = get_cell_type_from_pin(pin_name)  # Placeholder
            
            fanin = counts['fanin'].get(pin_name, 0)
            fanout = counts['fanout'].get(pin_name, 0)
            
            writer.writerow([node_id, pin_name, fanin, fanout, cell_type, pin_role])
    
    print(f"  Generated {len(sorted_pins)} rows")
    
    # Statistics
    pins_in_both = arrival_pins & nodes
    pins_only_arrival = arrival_pins - nodes
    pins_only_dot = nodes - arrival_pins
    
    print(f"\nStatistics:")
    print(f"  Pins in both arrival.txt and graph.dot: {len(pins_in_both)}")
    print(f"  Pins only in arrival.txt: {len(pins_only_arrival)}")
    print(f"  Pins only in graph.dot: {len(pins_only_dot)}")
    
    if pins_only_arrival:
        print(f"\n  [NOTE] {len(pins_only_arrival)} pins in arrival.txt but not in graph.dot")
        print(f"         Sample: {list(pins_only_arrival)[:5]}")
    
    if pins_only_dot:
        print(f"\n  [NOTE] {len(pins_only_dot)} pins in graph.dot but not in arrival.txt")
        print(f"         Sample: {list(pins_only_dot)[:5]}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python generate_node_static.py <graph.dot> <arrival.txt> <output.csv>")
        sys.exit(1)
    
    dot_file = Path(sys.argv[1])
    arrival_file = Path(sys.argv[2])
    output_file = Path(sys.argv[3])
    
    if not dot_file.exists():
        print(f"Error: {dot_file} not found")
        sys.exit(1)
    
    if not arrival_file.exists():
        print(f"Error: {arrival_file} not found")
        sys.exit(1)
    
    generate_node_static(dot_file, arrival_file, output_file)

