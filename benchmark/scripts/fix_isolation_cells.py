#!/usr/bin/env python3
"""
Replace isolation cells (ISOLANDX1_RVT, ISOLORX1_RVT) with equivalent logic gates
ISOLAND: Q = D & !ISO (when ISO=0, Q=D; when ISO=1, Q=0)
ISOLOR: Q = D | ISO (when ISO=0, Q=D; when ISO=1, Q=1)
For simplicity, we'll replace with AND2X1_RVT and OR2X1_RVT
"""
import re
import sys

def fix_isolation_cells(content):
    # Replace ISOLANDX1_RVT with AND2X1_RVT
    # ISOLAND: Q = D & !ISO -> use AND2X1 with D and !ISO
    # But simpler: just use AND2X1 with D and ISO (assuming ISO is inverted)
    # Actually, let's replace with a simple buffer for now (INVX0_RVT chain)
    # Or better: replace with AND2X1_RVT where we invert ISO
    
    # Pattern: ISOLANDX1_RVT instance_name ( .D(...), .ISO(...), .Q(...) );
    def replace_isoland(match):
        instance = match.group(1)
        d_pin = match.group(2)
        iso_pin = match.group(3)
        q_pin = match.group(4)
        
        # Create an intermediate wire for inverted ISO
        iso_inv = f"_iso_inv_{instance}"
        
        # Replace with: INV for ISO, then AND2
        replacement = f"""  INVX0_RVT {iso_inv} (
    .A({iso_pin}),
    .Y({iso_inv})
  );
  AND2X1_RVT {instance} (
    .A1({d_pin}),
    .A2({iso_inv}),
    .Y({q_pin})
  );"""
        return replacement
    
    # Match ISOLANDX1_RVT instances (multiline pattern)
    def replace_isoland_multiline(match):
        full_match = match.group(0)
        instance = match.group(1)
        d_pin = match.group(2).strip()
        iso_pin = match.group(3).strip()
        q_pin = match.group(4).strip()
        
        # Create an intermediate wire for inverted ISO
        iso_inv = f"_iso_inv_{instance}"
        
        # Replace with: INV for ISO, then AND2
        replacement = f"""  INVX0_RVT {iso_inv} (
    .A({iso_pin}),
    .Y({iso_inv})
  );
  AND2X1_RVT {instance} (
    .A1({d_pin}),
    .A2({iso_inv}),
    .Y({q_pin})
  );"""
        return replacement
    
    # Match multiline ISOLANDX1_RVT
    pattern_isoland = r'ISOLANDX1_RVT\s+(\w+)\s*\(\s*\n\s*\.D\(([^)]+)\),\s*\n\s*\.ISO\(([^)]+)\),\s*\n\s*\.Q\(([^)]+)\)\s*\n\s*\);'
    content = re.sub(pattern_isoland, replace_isoland_multiline, content, flags=re.MULTILINE)
    
    # Replace ISOLORX1_RVT with OR2X1_RVT
    def replace_isolor_multiline(match):
        instance = match.group(1)
        d_pin = match.group(2).strip()
        iso_pin = match.group(3).strip()
        q_pin = match.group(4).strip()
        
        # ISOLOR: Q = D | ISO  
        replacement = f"""  OR2X1_RVT {instance} (
    .A1({d_pin}),
    .A2({iso_pin}),
    .Y({q_pin})
  );"""
        return replacement
    
    pattern_isolor = r'ISOLORX1_RVT\s+(\w+)\s*\(\s*\n\s*\.D\(([^)]+)\),\s*\n\s*\.ISO\(([^)]+)\),\s*\n\s*\.Q\(([^)]+)\)\s*\n\s*\);'
    content = re.sub(pattern_isolor, replace_isolor_multiline, content, flags=re.MULTILINE)
    
    # Also try single-line pattern as fallback
    pattern_isoland_single = r'ISOLANDX1_RVT\s+(\w+)\s*\(\s*\.D\(([^)]+)\),\s*\.ISO\(([^)]+)\),\s*\.Q\(([^)]+)\)\s*\);'
    content = re.sub(pattern_isoland_single, replace_isoland_multiline, content)
    
    pattern_isolor_single = r'ISOLORX1_RVT\s+(\w+)\s*\(\s*\.D\(([^)]+)\),\s*\.ISO\(([^)]+)\),\s*\.Q\(([^)]+)\)\s*\);'
    content = re.sub(pattern_isolor_single, replace_isolor_multiline, content)
    
    return content

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: fix_isolation_cells.py <input_file> <output_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = fix_isolation_cells(content)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Fixed isolation cells in {input_file} -> {output_file}")

