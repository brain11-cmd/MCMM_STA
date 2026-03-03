#!/usr/bin/env python3
"""Generate node_static.csv from dump_pin_static output."""
import csv
import sys
import re
from pathlib import Path
from typing import Dict

def parse_pin_static(pin_static_file: Path) -> Dict[str, Dict]:
    """Parse dump_pin_static output."""
    pin_data = {}
    
    with open(pin_static_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Find header line
    header_line_idx = None
    for i, line in enumerate(lines):
        if 'Pin' in line and 'Fanin' in line and 'CellType' in line:
            header_line_idx = i
            break
    
    if header_line_idx is None:
        print(f"Error: Could not find header in {pin_static_file}")
        return pin_data
    
    # Parse data lines (skip separator lines)
    for line in lines[header_line_idx + 2:]:
        line = line.strip()
        if not line or line.startswith('-'):
            continue
        
        # Parse: "  _387_:CLK           3           5           DFFX1_RVT         CLK"
        parts = line.split()
        if len(parts) >= 5:
            pin_name = parts[0]
            try:
                fanin = int(parts[1])
                fanout = int(parts[2])
                cell_type = parts[3]
                pin_role = parts[4] if len(parts) > 4 else "N/A"
                
                pin_data[pin_name] = {
                    'fanin': fanin,
                    'fanout': fanout,
                    'cell_type': cell_type,
                    'pin_role': pin_role
                }
            except (ValueError, IndexError):
                continue
    
    return pin_data

def generate_node_static(
    pin_static_file: Path,
    arrival_file: Path,
    output_file: Path
):
    """Generate node_static.csv from dump_pin_static and arrival.txt."""
    
    print(f"Parsing pin_static.txt: {pin_static_file}")
    pin_data = parse_pin_static(pin_static_file)
    print(f"  Found {len(pin_data)} pins with static info")
    
    # Get pins from arrival.txt (authoritative pin set)
    print(f"\nParsing arrival.txt: {arrival_file}")
    arrival_pins = set()
    with open(arrival_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('Arrival') or line.startswith('-') or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 5:
                pin_name = parts[-1]
                if pin_name.lower() not in ['pin', 'e/r', 'e/f', 'l/r', 'l/f']:
                    arrival_pins.add(pin_name)
    
    print(f"  Found {len(arrival_pins)} pins in arrival.txt")
    
    # Merge: use arrival_pins as base, fill in static data where available
    all_pins = arrival_pins | set(pin_data.keys())
    sorted_pins = sorted(all_pins)
    
    print(f"\nGenerating node_static.csv: {output_file}")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['node_id', 'pin_name', 'fanin', 'fanout', 'cell_type', 'pin_role'])
        
        missing_static = 0
        for node_id, pin_name in enumerate(sorted_pins, start=0):
            if pin_name in pin_data:
                data = pin_data[pin_name]
                writer.writerow([
                    node_id,
                    pin_name,
                    data['fanin'],
                    data['fanout'],
                    data['cell_type'],
                    data['pin_role']
                ])
            else:
                # Pin not in pin_static (shouldn't happen, but handle gracefully)
                missing_static += 1
                writer.writerow([node_id, pin_name, 0, 0, "N/A", "N/A"])
    
    print(f"  Generated {len(sorted_pins)} rows")
    if missing_static > 0:
        print(f"  [WARNING] {missing_static} pins missing static data")
    
    # Statistics
    cell_types = {}
    for pin_name, data in pin_data.items():
        ct = data['cell_type']
        cell_types[ct] = cell_types.get(ct, 0) + 1
    
    print(f"\nCell type statistics:")
    for ct, count in sorted(cell_types.items(), key=lambda x: -x[1])[:10]:
        print(f"  {ct}: {count} pins")
    if len(cell_types) > 10:
        print(f"  ... and {len(cell_types) - 10} more cell types")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python generate_node_static_from_dump.py <pin_static.txt> <arrival.txt> <output.csv>")
        sys.exit(1)
    
    pin_static_file = Path(sys.argv[1])
    arrival_file = Path(sys.argv[2])
    output_file = Path(sys.argv[3])
    
    if not pin_static_file.exists():
        print(f"Error: {pin_static_file} not found")
        sys.exit(1)
    
    if not arrival_file.exists():
        print(f"Error: {arrival_file} not found")
        sys.exit(1)
    
    generate_node_static(pin_static_file, arrival_file, output_file)


