#!/usr/bin/env python3
"""比较两个备份文件的区别"""
import json
from pathlib import Path
from collections import Counter

backup1 = Path("D:/bishe_database/benchmark/test_output/gcd/anchor_corners/tt0p85v25c/train/arc_delay.json.backup")
backup2 = Path("D:/bishe_database/benchmark/test_output/gcd/anchor_corners/tt0p85v25c/train/arc_delay.json.backup2")

print("=" * 60)
print("Comparing Backup Files")
print("=" * 60)

# 读取文件
print(f"\n[Step 1] Reading files...")
with open(backup1, 'r', encoding='utf-8') as f:
    data1 = json.load(f)

with open(backup2, 'r', encoding='utf-8') as f:
    data2 = json.load(f)

arcs1 = data1.get('arcs', [])
arcs2 = data2.get('arcs', [])

print(f"  backup: {len(arcs1)} arcs")
print(f"  backup2: {len(arcs2)} arcs")
print(f"  Same corner: {data1.get('corner') == data2.get('corner')}")
print(f"  Same time_unit: {data1.get('time_unit') == data2.get('time_unit')}")

# 比较 edge_id
print(f"\n[Step 2] Comparing edge_id...")
edge_ids1 = [a['edge_id'] for a in arcs1]
edge_ids2 = [a['edge_id'] for a in arcs2]

print(f"  backup edge_id range: {min(edge_ids1)} - {max(edge_ids1)}")
print(f"  backup2 edge_id range: {min(edge_ids2)} - {max(edge_ids2)}")
print(f"  backup unique edge_ids: {len(set(edge_ids1))}")
print(f"  backup2 unique edge_ids: {len(set(edge_ids2))}")

# 比较 (src, dst, edge_type)
print(f"\n[Step 3] Comparing (src, dst, edge_type)...")
keys1 = {(a['src'], a['dst'], a['edge_type']) for a in arcs1}
keys2 = {(a['src'], a['dst'], a['edge_type']) for a in arcs2}

print(f"  backup unique keys: {len(keys1)}")
print(f"  backup2 unique keys: {len(keys2)}")
print(f"  Common keys: {len(keys1 & keys2)}")
print(f"  Only in backup: {len(keys1 - keys2)}")
print(f"  Only in backup2: {len(keys2 - keys1)}")

# 检查是否有重复
print(f"\n[Step 4] Checking duplicates...")
dup1 = [k for k, v in Counter(keys1).items() if v > 1]
dup2 = [k for k, v in Counter(keys2).items() if v > 1]

print(f"  backup duplicate keys: {len(dup1)}")
print(f"  backup2 duplicate keys: {len(dup2)}")

if dup1:
    print(f"  Sample duplicates in backup (first 3):")
    for key in dup1[:3]:
        matching = [a for a in arcs1 if (a['src'], a['dst'], a['edge_type']) == key]
        print(f"    {key}: {len(matching)} arcs with edge_ids: {[a['edge_id'] for a in matching]}")

if dup2:
    print(f"  Sample duplicates in backup2 (first 3):")
    for key in dup2[:3]:
        matching = [a for a in arcs2 if (a['src'], a['dst'], a['edge_type']) == key]
        print(f"    {key}: {len(matching)} arcs with edge_ids: {[a['edge_id'] for a in matching]}")

# 检查文件大小
print(f"\n[Step 5] File sizes...")
size1 = backup1.stat().st_size
size2 = backup2.stat().st_size
print(f"  backup size: {size1:,} bytes ({size1/1024:.1f} KB)")
print(f"  backup2 size: {size2:,} bytes ({size2/1024:.1f} KB)")
print(f"  Size difference: {abs(size1 - size2):,} bytes")

print("\n" + "=" * 60)
print("Summary:")
print(f"  backup: Original file (before canonicalization)")
print(f"  backup2: File after first canonicalization (before edge_id alignment)")
print("=" * 60)

