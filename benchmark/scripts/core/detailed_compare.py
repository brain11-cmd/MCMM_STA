#!/usr/bin/env python3
import json

f1 = json.load(open(r'D:\bishe_database\benchmark\test_output\gcd\anchor_corners\tt0p85v25c\train\arc_delay.json.backup2'))
f2 = json.load(open(r'D:\bishe_database\benchmark\test_output\gcd\corners\tt0p85v25c\arc_delay.json'))

arcs1 = {a['edge_id']: a for a in f1['arcs']}
arcs2 = {a['edge_id']: a for a in f2['arcs']}

print(f"File1 has {len(arcs1)} arcs")
print(f"File2 has {len(arcs2)} arcs")

# 检查edge_id=24
if 24 in arcs1 and 24 in arcs2:
    a1 = arcs1[24]
    a2 = arcs2[24]
    print(f"\nEdge_id=24 comparison:")
    print(f"  File1: src={a1['src']}, dst={a1['dst']}, mask={a1['mask']}")
    print(f"  File2: src={a2['src']}, dst={a2['dst']}, mask={a2['mask']}")
    print(f"  Identical: {a1 == a2}")

# 找出所有不同的arcs
diffs = []
for eid in sorted(set(arcs1.keys()) | set(arcs2.keys())):
    if eid not in arcs1:
        diffs.append((eid, 'only_in_file2', None, arcs2[eid]))
    elif eid not in arcs2:
        diffs.append((eid, 'only_in_file1', arcs1[eid], None))
    else:
        a1 = arcs1[eid]
        a2 = arcs2[eid]
        if a1 != a2:
            diffs.append((eid, 'different', a1, a2))

print(f"\nTotal differences: {len(diffs)}")
if diffs:
    print("First 10 differences:")
    for eid, reason, a1, a2 in diffs[:10]:
        print(f"  edge_id={eid}, reason={reason}")
        if reason == 'different':
            if a1['src'] != a2['src'] or a1['dst'] != a2['dst']:
                print(f"    src/dst: {a1['src']}->{a1['dst']} vs {a2['src']}->{a2['dst']}")
            if a1['mask'] != a2['mask']:
                print(f"    mask: {a1['mask']} vs {a2['mask']}")
            if a1['delay'] != a2['delay']:
                print(f"    delay: {a1['delay']} vs {a2['delay']}")






















