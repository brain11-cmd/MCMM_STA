#!/usr/bin/env python3
"""Analyze arc_delay.txt output from OpenTimer dump_arc_delay command"""

import sys
import re

def analyze_arc_delay(filepath):
    """Analyze arc_delay.txt file"""
    
    net_arcs = []
    cell_arcs = []
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Find header line
    header_idx = -1
    for i, line in enumerate(lines):
        if 'From' in line and 'To' in line and 'Type' in line:
            header_idx = i
            break
    
    if header_idx == -1:
        print("Error: Could not find header line")
        return
    
    # Parse data lines
    for line in lines[header_idx + 2:]:  # Skip header and separator
        line = line.strip()
        if not line or line.startswith('-'):
            continue
        
        # Parse: From To Type dRR dRF dFR dFF mRR mRF mFR mFF
        parts = line.split()
        if len(parts) < 11:
            continue
        
        from_pin = parts[0]
        to_pin = parts[1]
        arc_type = parts[2]
        dRR = float(parts[3])
        dRF = float(parts[4])
        dFR = float(parts[5])
        dFF = float(parts[6])
        mRR = int(parts[7])
        mRF = int(parts[8])
        mFR = int(parts[9])
        mFF = int(parts[10])
        
        arc_info = {
            'from': from_pin,
            'to': to_pin,
            'dRR': dRR, 'dRF': dRF, 'dFR': dFR, 'dFF': dFF,
            'mRR': mRR, 'mRF': mRF, 'mFR': mFR, 'mFF': mFF
        }
        
        if arc_type == 'net':
            net_arcs.append(arc_info)
        elif arc_type == 'cell':
            cell_arcs.append(arc_info)
    
    # Statistics
    print("=" * 60)
    print("Arc Delay Analysis")
    print("=" * 60)
    print(f"\nTotal arcs: {len(net_arcs) + len(cell_arcs)}")
    print(f"  Net arcs: {len(net_arcs)}")
    print(f"  Cell arcs: {len(cell_arcs)}")
    
    # Net Arc Statistics
    print("\n" + "=" * 60)
    print("Net Arc Statistics")
    print("=" * 60)
    
    net_with_rr = sum(1 for a in net_arcs if a['mRR'] == 1)
    net_with_ff = sum(1 for a in net_arcs if a['mFF'] == 1)
    net_with_rr_or_ff = sum(1 for a in net_arcs if a['mRR'] == 1 or a['mFF'] == 1)
    net_with_rf = sum(1 for a in net_arcs if a['mRF'] == 1)
    net_with_fr = sum(1 for a in net_arcs if a['mFR'] == 1)
    net_nonzero_rr = sum(1 for a in net_arcs if a['mRR'] == 1 and a['dRR'] > 0)
    net_nonzero_ff = sum(1 for a in net_arcs if a['mFF'] == 1 and a['dFF'] > 0)
    
    print(f"Net arcs with valid RR: {net_with_rr} ({net_with_rr/len(net_arcs)*100:.1f}%)")
    print(f"Net arcs with valid FF: {net_with_ff} ({net_with_ff/len(net_arcs)*100:.1f}%)")
    print(f"Net arcs with valid RR or FF: {net_with_rr_or_ff} ({net_with_rr_or_ff/len(net_arcs)*100:.1f}%)")
    print(f"Net arcs with RF (should be 0): {net_with_rf} ({net_with_rf/len(net_arcs)*100:.1f}%)")
    print(f"Net arcs with FR (should be 0): {net_with_fr} ({net_with_fr/len(net_arcs)*100:.1f}%)")
    print(f"Net arcs with non-zero RR: {net_nonzero_rr} ({net_nonzero_rr/len(net_arcs)*100:.1f}%)")
    print(f"Net arcs with non-zero FF: {net_nonzero_ff} ({net_nonzero_ff/len(net_arcs)*100:.1f}%)")
    
    # Sample net arcs with valid delays
    print("\nSample Net Arcs with valid delays:")
    sample_count = 0
    for a in net_arcs:
        if (a['mRR'] == 1 and a['dRR'] > 0) or (a['mFF'] == 1 and a['dFF'] > 0):
            print(f"  {a['from']} -> {a['to']}: RR={a['dRR']:.6f}(m={a['mRR']}), FF={a['dFF']:.6f}(m={a['mFF']})")
            sample_count += 1
            if sample_count >= 5:
                break
    
    # Cell Arc Statistics
    print("\n" + "=" * 60)
    print("Cell Arc Statistics")
    print("=" * 60)
    
    cell_with_rr = sum(1 for a in cell_arcs if a['mRR'] == 1)
    cell_with_rf = sum(1 for a in cell_arcs if a['mRF'] == 1)
    cell_with_fr = sum(1 for a in cell_arcs if a['mFR'] == 1)
    cell_with_ff = sum(1 for a in cell_arcs if a['mFF'] == 1)
    cell_with_all4 = sum(1 for a in cell_arcs if a['mRR'] == 1 and a['mRF'] == 1 and a['mFR'] == 1 and a['mFF'] == 1)
    cell_with_any = sum(1 for a in cell_arcs if a['mRR'] == 1 or a['mRF'] == 1 or a['mFR'] == 1 or a['mFF'] == 1)
    
    print(f"Cell arcs with valid RR: {cell_with_rr} ({cell_with_rr/len(cell_arcs)*100:.1f}%)")
    print(f"Cell arcs with valid RF: {cell_with_rf} ({cell_with_rf/len(cell_arcs)*100:.1f}%)")
    print(f"Cell arcs with valid FR: {cell_with_fr} ({cell_with_fr/len(cell_arcs)*100:.1f}%)")
    print(f"Cell arcs with valid FF: {cell_with_ff} ({cell_with_ff/len(cell_arcs)*100:.1f}%)")
    print(f"Cell arcs with all 4 channels: {cell_with_all4} ({cell_with_all4/len(cell_arcs)*100:.1f}%)")
    print(f"Cell arcs with any valid channel: {cell_with_any} ({cell_with_any/len(cell_arcs)*100:.1f}%)")
    
    # Sample cell arcs with valid delays
    print("\nSample Cell Arcs with valid delays:")
    sample_count = 0
    for a in cell_arcs:
        if a['mRR'] == 1 or a['mRF'] == 1 or a['mFR'] == 1 or a['mFF'] == 1:
            print(f"  {a['from']} -> {a['to']}: RR={a['dRR']:.6f}(m={a['mRR']}), RF={a['dRF']:.6f}(m={a['mRF']}), FR={a['dFR']:.6f}(m={a['mFR']}), FF={a['dFF']:.6f}(m={a['mFF']})")
            sample_count += 1
            if sample_count >= 5:
                break
    
    print("\n" + "=" * 60)
    print("Validation")
    print("=" * 60)
    
    # Check Net Arc RF/FR (should all be 0)
    net_rf_errors = sum(1 for a in net_arcs if a['mRF'] == 1)
    net_fr_errors = sum(1 for a in net_arcs if a['mFR'] == 1)
    
    if net_rf_errors == 0 and net_fr_errors == 0:
        print("[OK] Net Arc RF/FR mask validation: PASSED (all 0 as expected)")
    else:
        print(f"[FAIL] Net Arc RF/FR mask validation: FAILED")
        print(f"   Found {net_rf_errors} net arcs with RF mask=1 (should be 0)")
        print(f"   Found {net_fr_errors} net arcs with FR mask=1 (should be 0)")
    
    print("\n[OK] Analysis complete!")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python analyze_arc_delay.py <arc_delay.txt>")
        sys.exit(1)
    
    analyze_arc_delay(sys.argv[1])

