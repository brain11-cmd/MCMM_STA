#!/usr/bin/env python3
"""Check cell_type distribution in node_static.csv."""
import csv
import sys
from pathlib import Path
from collections import Counter

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_cell_types.py <node_static.csv>")
        sys.exit(1)
    
    csv_file = Path(sys.argv[1])
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    cell_types = Counter(r['cell_type'] for r in rows)
    
    print(f"Cell Type Distribution (Total: {len(rows)} pins)")
    print("=" * 60)
    for ct, count in cell_types.most_common():
        pct = count / len(rows) * 100
        print(f"  {ct:25s}: {count:4d} ({pct:5.1f}%)")
    
    # Check for instance names (should not exist)
    instance_names = [ct for ct in cell_types.keys() if ct.startswith('_') and ct.endswith('_')]
    if instance_names:
        print(f"\n[WARNING] Found {len(instance_names)} instance names (should be cell types):")
        for iname in instance_names[:5]:
            print(f"  {iname}")
    else:
        print(f"\n[OK] No instance names found - all cell_types are master cell names!")


