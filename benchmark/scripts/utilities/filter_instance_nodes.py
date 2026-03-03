#!/usr/bin/env python3
"""Filter out __INSTANCE__ nodes from node_static.csv for training."""
import csv
import sys
from pathlib import Path

def filter_instance_nodes(input_file: Path, output_file: Path):
    """Filter out __INSTANCE__ nodes and renumber node_id."""
    
    print(f"Reading: {input_file}")
    all_rows = []
    instance_rows = []
    real_pin_rows = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_rows.append(row)
            if row['cell_type'] == '__INSTANCE__':
                instance_rows.append(row)
            else:
                real_pin_rows.append(row)
    
    print(f"  Total nodes: {len(all_rows)}")
    print(f"  __INSTANCE__ nodes: {len(instance_rows)}")
    print(f"  Real pins: {len(real_pin_rows)}")
    
    # Sort real pins by pin_name for stable node_id
    real_pin_rows.sort(key=lambda r: r['pin_name'])
    
    # Renumber node_id
    print(f"\nGenerating training node set: {output_file}")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['node_id', 'pin_name', 'fanin', 'fanout', 'cell_type', 'pin_role'])
        
        for new_node_id, row in enumerate(real_pin_rows):
            writer.writerow([
                new_node_id,
                row['pin_name'],
                row['fanin'],
                row['fanout'],
                row['cell_type'],
                row['pin_role']
            ])
    
    print(f"  Wrote {len(real_pin_rows)} rows (filtered out {len(instance_rows)} __INSTANCE__ nodes)")
    
    # Statistics
    cell_types = {}
    for row in real_pin_rows:
        ct = row['cell_type']
        cell_types[ct] = cell_types.get(ct, 0) + 1
    
    print(f"\nCell type distribution (after filtering):")
    for ct, count in sorted(cell_types.items(), key=lambda x: -x[1]):
        print(f"  {ct:20s}: {count:4d} ({count/len(real_pin_rows)*100:5.1f}%)")
    
    # Check for remaining N/A
    na_count = sum(1 for r in real_pin_rows if r['cell_type'] == 'N/A')
    if na_count > 0:
        print(f"\n[WARNING] Found {na_count} pins with cell_type = N/A (should be classified)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python filter_instance_nodes.py <input.csv> <output.csv>")
        print("  Example: python filter_instance_nodes.py node_static.csv node_static_train.csv")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)
    
    filter_instance_nodes(input_file, output_file)


