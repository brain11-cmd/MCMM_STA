#!/usr/bin/env python3
"""Analyze arrival.txt to count valid vs n/a values."""
import re
import sys
from pathlib import Path

def analyze_arrival(arrival_file):
    """Analyze arrival.txt file."""
    with open(arrival_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    valid_count = 0
    n_a_count = 0
    total_pins = 0
    
    # Skip header (first 4 lines)
    for line in lines[4:]:
        line = line.strip()
        if not line or line.startswith('-'):
            continue
        
        parts = line.split()
        if len(parts) < 5:
            continue
        
        total_pins += 1
        # Check first 4 columns (E/R, E/F, L/R, L/F)
        arrival_values = parts[:4]
        
        has_valid = any(re.match(r'^\d+\.?\d*$', val) for val in arrival_values)
        all_na = all('n/a' in val for val in arrival_values)
        
        if has_valid:
            valid_count += 1
        elif all_na:
            n_a_count += 1
    
    print(f"Arrival Analysis for: {arrival_file}")
    print("=" * 60)
    print(f"Total pins: {total_pins}")
    print(f"Pins with valid arrival: {valid_count} ({valid_count/total_pins*100:.1f}%)")
    print(f"Pins with all n/a: {n_a_count} ({n_a_count/total_pins*100:.1f}%)")
    print("=" * 60)
    
    return {
        "total": total_pins,
        "valid": valid_count,
        "n_a": n_a_count,
        "valid_ratio": valid_count / total_pins if total_pins > 0 else 0.0
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_arrival.py <arrival.txt>")
        sys.exit(1)
    
    arrival_file = Path(sys.argv[1])
    if not arrival_file.exists():
        print(f"Error: File not found: {arrival_file}")
        sys.exit(1)
    
    analyze_arrival(arrival_file)


