#!/usr/bin/env python3
"""Generate node_static.csv from pin_static.txt (OpenTimer dump_pin_static output)."""
import re
import sys
import csv
from pathlib import Path
from typing import Dict, List

def parse_pin_static(pin_static_file: Path) -> List[Dict]:
    """Parse pin_static.txt to extract pin information."""
    pins = []
    
    with open(pin_static_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Find the header line
    header_line = None
    for i, line in enumerate(lines):
        if 'Pin' in line and 'Fanin' in line and 'Fanout' in line:
            header_line = i
            break
    
    if header_line is None:
        print("Error: Could not find header line in pin_static.txt")
        return []
    
    # Parse data lines (skip header and separator lines)
    for line in lines[header_line + 2:]:  # Skip header and separator
        line = line.strip()
        if not line or line.startswith('-') or line.startswith('Pin Static'):
            continue
        
        # Parse format: "  _387_:CLK           3           5           DFFX1_RVT         CLK"
        # Or: "     _187_:           0           4                 N/A         N/A"
        parts = line.split()
        if len(parts) < 5:
            continue
        
        # Pin name is the first non-empty part (may have spaces in quotes, but usually first)
        # Find where the numbers start (fanin)
        pin_name = None
        fanin_idx = None
        
        for i, part in enumerate(parts):
            # Check if this part looks like a number (fanin)
            if part.isdigit():
                fanin_idx = i
                # Pin name is everything before this
                pin_name = ' '.join(parts[:i]).strip()
                break
        
        if pin_name is None or fanin_idx is None:
            continue
        
        # Extract fields
        try:
            fanin = int(parts[fanin_idx])
            fanout = int(parts[fanin_idx + 1])
            cell_type = parts[fanin_idx + 2] if fanin_idx + 2 < len(parts) else "N/A"
            pin_role = parts[fanin_idx + 3] if fanin_idx + 3 < len(parts) else "N/A"
            
            # Handle N/A cell_type: classify as __INSTANCE__ if pin_name ends with ':'
            if cell_type == "N/A" and pin_name.endswith(':') and ':' in pin_name:
                cell_type = "__INSTANCE__"
            
            pins.append({
                'pin_name': pin_name,
                'fanin': fanin,
                'fanout': fanout,
                'cell_type': cell_type,
                'pin_role': pin_role
            })
        except (ValueError, IndexError) as e:
            print(f"Warning: Failed to parse line: {line[:60]}... ({e})")
            continue
    
    return pins

def generate_node_static(pin_static_file: Path, output_file: Path):
    """Generate node_static.csv from pin_static.txt."""
    
    print(f"Parsing pin_static.txt: {pin_static_file}")
    pins = parse_pin_static(pin_static_file)
    print(f"  Found {len(pins)} pins")
    
    if not pins:
        print("Error: No pins found in pin_static.txt")
        return
    
    # Sort pins by pin_name for stable node_id assignment
    sorted_pins = sorted(pins, key=lambda p: p['pin_name'])
    
    # Generate node_static.csv
    print(f"\nGenerating node_static.csv: {output_file}")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['node_id', 'pin_name', 'fanin', 'fanout', 'cell_type', 'pin_role'])
        
        for node_id, pin in enumerate(sorted_pins):
            writer.writerow([
                node_id,
                pin['pin_name'],
                pin['fanin'],
                pin['fanout'],
                pin['cell_type'],
                pin['pin_role']
            ])
    
    print(f"  Generated {len(sorted_pins)} rows")
    
    # Statistics
    cell_types = {}
    for pin in pins:
        ct = pin['cell_type']
        cell_types[ct] = cell_types.get(ct, 0) + 1
    
    print(f"\nCell type distribution:")
    for ct, count in sorted(cell_types.items(), key=lambda x: -x[1]):
        print(f"  {ct:20s}: {count:4d} ({count/len(pins)*100:5.1f}%)")
    
    # Check for N/A
    na_count = sum(1 for p in pins if p['cell_type'] == 'N/A')
    if na_count > 0:
        print(f"\n[WARNING] Found {na_count} pins with cell_type = N/A")
        print("  These should be classified (e.g., __INSTANCE__, __PORT__, __UNKNOWN__)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_node_static_from_pin_static.py <pin_static.txt> <output.csv>")
        sys.exit(1)
    
    pin_static_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not pin_static_file.exists():
        print(f"Error: {pin_static_file} not found")
        sys.exit(1)
    
    generate_node_static(pin_static_file, output_file)


