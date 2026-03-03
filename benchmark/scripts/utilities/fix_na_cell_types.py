#!/usr/bin/env python3
"""Fix N/A cell_types by classifying them into proper categories."""
import csv
import sys
import re
from pathlib import Path
from typing import Dict

def classify_na_pin(pin_name: str, fanin: int, fanout: int, pin_role: str) -> str:
    """Classify N/A pin into proper category."""
    
    # Pattern 1: Instance body node (gate_name: with no pin role)
    # Format: "_187_:" (ends with colon, no pin name after)
    if pin_name.endswith(':') and ':' in pin_name and len(pin_name.split(':')) == 2:
        # This is a gate instance body node
        # Extract gate name to get cell type (but we don't have it here)
        # For now, mark as __INSTANCE__
        return "__INSTANCE__"
    
    # Pattern 2: Port-like (no instance prefix)
    if '/' not in pin_name and ':' not in pin_name:
        # Check if it's a common port name
        port_patterns = ['clk', 'reset', 'in', 'out', 'req', 'resp', 'val', 'rdy']
        pin_lower = pin_name.lower()
        for pattern in port_patterns:
            if pattern in pin_lower:
                return "__PORT__"
        return "__PORT__"  # Default for ports
    
    # Pattern 3: Has colon but no pin role (shouldn't happen if parsing is correct)
    if ':' in pin_name and not pin_name.endswith(':'):
        # This might be a parsing issue
        return "__UNKNOWN__"
    
    # Pattern 4: Default unknown
    return "__UNKNOWN__"

def fix_node_static(input_file: Path, output_file: Path):
    """Fix N/A cell_types in node_static.csv."""
    
    print(f"Reading: {input_file}")
    rows = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"  Found {len(rows)} pins")
    
    # Fix N/A cell_types
    fixed_count = 0
    classification = {}
    
    for row in rows:
        if row['cell_type'] == 'N/A':
            new_type = classify_na_pin(
                row['pin_name'],
                int(row['fanin']),
                int(row['fanout']),
                row['pin_role']
            )
            row['cell_type'] = new_type
            fixed_count += 1
            classification[new_type] = classification.get(new_type, 0) + 1
    
    print(f"\nFixed {fixed_count} N/A cell_types:")
    for cat, count in sorted(classification.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    
    # Write fixed CSV
    print(f"\nWriting: {output_file}")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['node_id', 'pin_name', 'fanin', 'fanout', 'cell_type', 'pin_role']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"  Wrote {len(rows)} rows")
    
    # Final statistics
    cell_types = {}
    for row in rows:
        ct = row['cell_type']
        cell_types[ct] = cell_types.get(ct, 0) + 1
    
    print(f"\nFinal cell type distribution:")
    real_cells = {k: v for k, v in cell_types.items() if not k.startswith('__')}
    special_cells = {k: v for k, v in cell_types.items() if k.startswith('__')}
    
    print(f"  Real cell types: {len(real_cells)}")
    print(f"  Special types: {len(special_cells)}")
    for cat, count in sorted(special_cells.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fix_na_cell_types.py <input.csv> <output.csv>")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)
    
    fix_node_static(input_file, output_file)


