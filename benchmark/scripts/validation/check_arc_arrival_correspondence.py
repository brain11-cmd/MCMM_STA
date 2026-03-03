#!/usr/bin/env python3
"""Check correspondence between arrival.txt and arc_delay.json, and analyze duplicate edges."""

import json
import sys
from pathlib import Path
from collections import defaultdict


def normalize_pin_name(pin_name: str) -> str:
    """Normalize pin name."""
    return pin_name.strip()


def parse_arrival_txt(txt_file: Path) -> set:
    """Parse arrival.txt and return set of pin names."""
    pins = set()
    
    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('-') or line.startswith('Arrival') or 'E/R' in line:
                continue
            
            parts = line.split()
            if len(parts) >= 5:
                pin_name = normalize_pin_name(parts[-1])
                if pin_name:
                    pins.add(pin_name)
    
    return pins


def parse_arc_delay_txt(txt_file: Path) -> dict:
    """Parse arc_delay.txt and return edge counts and duplicates."""
    edges = defaultdict(list)
    invalid_edges = []
    
    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Find header
    header_idx = -1
    for i, line in enumerate(lines):
        if 'From' in line and 'To' in line and 'Type' in line:
            header_idx = i
            break
    
    if header_idx == -1:
        print(f"Error: Could not find header in {txt_file}")
        return {}
    
    # Parse data lines
    for line_num, line in enumerate(lines[header_idx + 2:], start=header_idx + 3):
        line = line.strip()
        if not line or line.startswith('-'):
            continue
        
        parts = line.split()
        if len(parts) < 3:
            continue
        
        from_pin = normalize_pin_name(parts[0])
        to_pin = normalize_pin_name(parts[1])
        
        # Check for invalid pin names (like "_387_:" without pin name)
        if ':' not in from_pin or ':' not in to_pin:
            invalid_edges.append((line_num, from_pin, to_pin))
            continue
        
        key = (from_pin, to_pin)
        edges[key].append({
            'line': line_num,
            'type': parts[2] if len(parts) > 2 else 'unknown',
            'dRR': float(parts[3]) if len(parts) > 3 else 0.0,
            'dRF': float(parts[4]) if len(parts) > 4 else 0.0,
            'dFR': float(parts[5]) if len(parts) > 5 else 0.0,
            'dFF': float(parts[6]) if len(parts) > 6 else 0.0,
            'mRR': int(parts[7]) if len(parts) > 7 else 0,
            'mRF': int(parts[8]) if len(parts) > 8 else 0,
            'mFR': int(parts[9]) if len(parts) > 9 else 0,
            'mFF': int(parts[10]) if len(parts) > 10 else 0,
        })
    
    return {
        'edges': dict(edges),
        'invalid_edges': invalid_edges
    }


def check_correspondence(arrival_file: Path, arc_delay_json: Path):
    """Check if pins in arrival.txt correspond to pins in arc_delay.json."""
    print("=" * 60)
    print("Checking Correspondence")
    print("=" * 60)
    
    # Parse arrival.txt
    arrival_pins = parse_arrival_txt(arrival_file)
    print(f"\narrival.txt: {len(arrival_pins)} pins")
    
    # Parse arc_delay.json
    with open(arc_delay_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    arcs = data.get('arcs', [])
    arc_pins = set()
    for arc in arcs:
        arc_pins.add(normalize_pin_name(arc.get('src', '')))
        arc_pins.add(normalize_pin_name(arc.get('dst', '')))
    
    print(f"arc_delay.json: {len(arcs)} arcs, {len(arc_pins)} unique pins")
    
    # Check correspondence
    pins_only_in_arrival = arrival_pins - arc_pins
    pins_only_in_arcs = arc_pins - arrival_pins
    common_pins = arrival_pins & arc_pins
    
    print(f"\nCorrespondence:")
    print(f"  Common pins: {len(common_pins)}")
    print(f"  Pins only in arrival.txt: {len(pins_only_in_arrival)}")
    print(f"  Pins only in arc_delay.json: {len(pins_only_in_arcs)}")
    
    if pins_only_in_arrival:
        print(f"\n  Sample pins only in arrival.txt (first 5):")
        for pin in list(pins_only_in_arrival)[:5]:
            print(f"    {pin}")
    
    if pins_only_in_arcs:
        print(f"\n  Sample pins only in arc_delay.json (first 5):")
        for pin in list(pins_only_in_arcs)[:5]:
            print(f"    {pin}")
    
    coverage = len(common_pins) / len(arrival_pins) * 100 if arrival_pins else 0
    print(f"\n  Coverage: {coverage:.2f}%")
    
    return len(common_pins) == len(arrival_pins) and len(pins_only_in_arcs) == 0


def analyze_duplicates(arc_delay_txt: Path):
    """Analyze duplicate edges in arc_delay.txt."""
    print("\n" + "=" * 60)
    print("Analyzing Duplicate Edges in arc_delay.txt")
    print("=" * 60)
    
    result = parse_arc_delay_txt(arc_delay_txt)
    edges = result['edges']
    invalid_edges = result['invalid_edges']
    
    total_edges = sum(len(occurrences) for occurrences in edges.values())
    unique_edges = len(edges)
    duplicate_edges = {k: v for k, v in edges.items() if len(v) > 1}
    
    print(f"\nStatistics:")
    print(f"  Total edge occurrences: {total_edges}")
    print(f"  Unique edges: {unique_edges}")
    print(f"  Duplicate edges: {len(duplicate_edges)}")
    print(f"  Invalid edges (missing pin name): {len(invalid_edges)}")
    
    if invalid_edges:
        print(f"\n  Sample invalid edges (first 5):")
        for line_num, from_pin, to_pin in invalid_edges[:5]:
            print(f"    Line {line_num}: '{from_pin}' -> '{to_pin}'")
    
    if duplicate_edges:
        print(f"\n  Sample duplicate edges (first 5):")
        for (from_pin, to_pin), occurrences in list(duplicate_edges.items())[:5]:
            print(f"\n    Edge: {from_pin} -> {to_pin} ({len(occurrences)} occurrences)")
            for occ in occurrences:
                has_value = (occ['mRR'] == 1 and occ['dRR'] != 0.0) or \
                           (occ['mRF'] == 1 and occ['dRF'] != 0.0) or \
                           (occ['mFR'] == 1 and occ['dFR'] != 0.0) or \
                           (occ['mFF'] == 1 and occ['dFF'] != 0.0)
                print(f"      Line {occ['line']}: type={occ['type']}, "
                      f"dRR={occ['dRR']:.6f}(m={occ['mRR']}), "
                      f"has_value={has_value}")
    
    # Analyze why duplicates exist
    print(f"\n  Duplicate analysis:")
    duplicates_with_value = 0
    duplicates_all_zero = 0
    
    for occurrences in duplicate_edges.values():
        has_any_value = False
        for occ in occurrences:
            if (occ['mRR'] == 1 and occ['dRR'] != 0.0) or \
               (occ['mRF'] == 1 and occ['dRF'] != 0.0) or \
               (occ['mFR'] == 1 and occ['dFR'] != 0.0) or \
               (occ['mFF'] == 1 and occ['dFF'] != 0.0):
                has_any_value = True
                break
        
        if has_any_value:
            duplicates_with_value += 1
        else:
            duplicates_all_zero += 1
    
    print(f"    Duplicates with at least one non-zero value: {duplicates_with_value}")
    print(f"    Duplicates all zero: {duplicates_all_zero}")
    print(f"\n  [NOTE] Duplicates with values should be kept (prefer non-zero)")
    print(f"  [NOTE] Duplicates all zero can be ignored")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python check_arc_arrival_correspondence.py <arrival.txt> <arc_delay.json> <arc_delay.txt>")
        sys.exit(1)
    
    arrival_file = Path(sys.argv[1])
    arc_delay_json = Path(sys.argv[2])
    arc_delay_txt = Path(sys.argv[3])
    
    if not arrival_file.exists():
        print(f"Error: {arrival_file} not found")
        sys.exit(1)
    
    if not arc_delay_json.exists():
        print(f"Error: {arc_delay_json} not found")
        sys.exit(1)
    
    if not arc_delay_txt.exists():
        print(f"Error: {arc_delay_txt} not found")
        sys.exit(1)
    
    # Check correspondence
    is_correspondent = check_correspondence(arrival_file, arc_delay_json)
    
    # Analyze duplicates
    analyze_duplicates(arc_delay_txt)
    
    print("\n" + "=" * 60)
    if is_correspondent:
        print("[OK] arrival.txt and arc_delay.json are well-corresponded")
    else:
        print("[WARNING] arrival.txt and arc_delay.json have mismatched pins")
    print("=" * 60)


