#!/usr/bin/env python3
"""Analyze N/A cell_type pins to determine their nature."""
import csv
import sys
import re
from pathlib import Path
from collections import Counter
from typing import List, Dict

def is_port_like(pin_name: str) -> bool:
    """Check if pin_name looks like a port (no instance prefix)."""
    # Port-like patterns: no underscore prefix, or common port names
    if '/' not in pin_name and ':' not in pin_name:
        return True
    
    # Common port names
    port_patterns = ['clk', 'reset', 'in', 'out', 'req', 'resp', 'val', 'rdy']
    pin_lower = pin_name.lower()
    for pattern in port_patterns:
        if pattern in pin_lower:
            return True
    
    return False

def analyze_na_pins(csv_file: Path) -> Dict:
    """Analyze pins with cell_type = N/A."""
    
    na_pins = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['cell_type'] == 'N/A':
                na_pins.append({
                    'pin_name': row['pin_name'],
                    'fanin': int(row['fanin']),
                    'fanout': int(row['fanout']),
                    'pin_role': row['pin_role']
                })
    
    print(f"Analyzing {len(na_pins)} pins with cell_type = N/A")
    print("=" * 80)
    
    # Statistics
    has_slash = sum(1 for p in na_pins if '/' in p['pin_name'])
    has_colon = sum(1 for p in na_pins if ':' in p['pin_name'])
    port_like = sum(1 for p in na_pins if is_port_like(p['pin_name']))
    
    print(f"\n1. Pin name patterns:")
    print(f"   Has '/': {has_slash} ({has_slash/len(na_pins)*100:.1f}%)")
    print(f"   Has ':': {has_colon} ({has_colon/len(na_pins)*100:.1f}%)")
    print(f"   Port-like: {port_like} ({port_like/len(na_pins)*100:.1f}%)")
    
    # Fanin/Fanout distribution
    fanin_zero = sum(1 for p in na_pins if p['fanin'] == 0)
    fanout_zero = sum(1 for p in na_pins if p['fanout'] == 0)
    both_zero = sum(1 for p in na_pins if p['fanin'] == 0 and p['fanout'] == 0)
    both_nonzero = sum(1 for p in na_pins if p['fanin'] > 0 and p['fanout'] > 0)
    
    print(f"\n2. Connectivity:")
    print(f"   Fanin = 0: {fanin_zero} ({fanin_zero/len(na_pins)*100:.1f}%)")
    print(f"   Fanout = 0: {fanout_zero} ({fanout_zero/len(na_pins)*100:.1f}%)")
    print(f"   Both = 0: {both_zero} ({both_zero/len(na_pins)*100:.1f}%)")
    print(f"   Both > 0: {both_nonzero} ({both_nonzero/len(na_pins)*100:.1f}%)")
    
    # Pin role distribution
    pin_roles = Counter(p['pin_role'] for p in na_pins)
    print(f"\n3. Pin role distribution:")
    for role, count in pin_roles.most_common(10):
        print(f"   {role}: {count}")
    
    # Sample pins by category
    print(f"\n4. Sample pins by category:")
    
    # Category 1: Port-like (no slash, no colon)
    port_pins = [p for p in na_pins if not ('/' in p['pin_name'] or ':' in p['pin_name'])]
    if port_pins:
        print(f"\n   [PORT-LIKE] ({len(port_pins)} pins):")
        for p in port_pins[:5]:
            print(f"     {p['pin_name']:30s} fanin={p['fanin']:2d} fanout={p['fanout']:2d} role={p['pin_role']}")
    
    # Category 2: Has colon but no slash (instance:pin format)
    colon_pins = [p for p in na_pins if ':' in p['pin_name'] and '/' not in p['pin_name']]
    if colon_pins:
        print(f"\n   [INSTANCE:PIN] ({len(colon_pins)} pins):")
        for p in colon_pins[:5]:
            print(f"     {p['pin_name']:30s} fanin={p['fanin']:2d} fanout={p['fanout']:2d} role={p['pin_role']}")
    
    # Category 3: Has slash (Inst/Pin format)
    slash_pins = [p for p in na_pins if '/' in p['pin_name']]
    if slash_pins:
        print(f"\n   [INST/PIN] ({len(slash_pins)} pins):")
        for p in slash_pins[:5]:
            print(f"     {p['pin_name']:30s} fanin={p['fanin']:2d} fanout={p['fanout']:2d} role={p['pin_role']}")
    
    # Category 4: Both fanin and fanout > 0 (internal nodes)
    internal_pins = [p for p in na_pins if p['fanin'] > 0 and p['fanout'] > 0]
    if internal_pins:
        print(f"\n   [INTERNAL] (fanin>0 and fanout>0, {len(internal_pins)} pins):")
        for p in internal_pins[:5]:
            print(f"     {p['pin_name']:30s} fanin={p['fanin']:2d} fanout={p['fanout']:2d} role={p['pin_role']}")
    
    # Category 5: Fanin=0 (sources)
    source_pins = [p for p in na_pins if p['fanin'] == 0]
    if source_pins:
        print(f"\n   [SOURCES] (fanin=0, {len(source_pins)} pins):")
        for p in source_pins[:5]:
            print(f"     {p['pin_name']:30s} fanin={p['fanin']:2d} fanout={p['fanout']:2d} role={p['pin_role']}")
    
    # Category 6: Fanout=0 (sinks)
    sink_pins = [p for p in na_pins if p['fanout'] == 0]
    if sink_pins:
        print(f"\n   [SINKS] (fanout=0, {len(sink_pins)} pins):")
        for p in sink_pins[:5]:
            print(f"     {p['pin_name']:30s} fanin={p['fanin']:2d} fanout={p['fanout']:2d} role={p['pin_role']}")
    
    return {
        'total': len(na_pins),
        'port_like': len(port_pins),
        'colon_format': len(colon_pins),
        'slash_format': len(slash_pins),
        'internal': len(internal_pins),
        'sources': len(source_pins),
        'sinks': len(sink_pins)
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_na_pins.py <node_static.csv>")
        sys.exit(1)
    
    csv_file = Path(sys.argv[1])
    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        sys.exit(1)
    
    analyze_na_pins(csv_file)


