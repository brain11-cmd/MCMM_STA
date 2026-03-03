#!/usr/bin/env python3
"""
比较同一 benchmark 不同 corner 的 pin_cap.txt，判断是否可以共享
"""
import re
from pathlib import Path
from collections import defaultdict

benchmark_dir = Path("D:/bishe_database/benchmark/test_output/gcd")
corners_dir = benchmark_dir / "anchor_corners"

print("=" * 60)
print("Comparing pin_cap.txt Across Corners")
print("=" * 60)

# 找到所有 corner 的 pin_cap.txt
print("\n[Step 1] Finding pin_cap.txt files...")
corner_pin_caps = {}
for corner_dir in corners_dir.iterdir():
    if not corner_dir.is_dir():
        continue
    
    pin_cap_file = corner_dir / "train" / "pin_cap.txt"
    if pin_cap_file.exists():
        corner_name = corner_dir.name
        print(f"  Found: {corner_name}/train/pin_cap.txt")
        
        # 读取 pin_cap.txt
        pin_caps = {}
        with open(pin_cap_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[3:]:  # skip header
                line = line.strip()
                if not line or line.startswith('-'):
                    continue
                
                parts = line.split()
                if len(parts) >= 5:
                    cap_values = tuple(float(x) for x in parts[:4])
                    pin_name = ' '.join(parts[4:]).strip()
                    pin_caps[pin_name] = cap_values
        
        corner_pin_caps[corner_name] = pin_caps
        print(f"    Loaded {len(pin_caps)} pins")

if len(corner_pin_caps) < 2:
    print("\n[ERROR] Need at least 2 corners to compare")
    exit(1)

# 比较不同 corner 的 pin_cap
print(f"\n[Step 2] Comparing {len(corner_pin_caps)} corners...")
corners = list(corner_pin_caps.keys())

# 找到所有 corner 共有的 pins
all_pins = set(corner_pin_caps[corners[0]].keys())
for corner in corners[1:]:
    all_pins &= set(corner_pin_caps[corner].keys())

print(f"  Common pins across all corners: {len(all_pins)}")

# 比较每个 pin 的电容值
print("\n[Step 3] Comparing capacitance values...")
identical_pins = []
different_pins = []

for pin_name in sorted(all_pins):
    caps = {corner: corner_pin_caps[corner][pin_name] for corner in corners}
    
    # 检查是否所有 corner 的值都相同
    first_cap = caps[corners[0]]
    all_same = all(caps[c] == first_cap for c in corners[1:])
    
    if all_same:
        identical_pins.append((pin_name, first_cap))
    else:
        different_pins.append((pin_name, caps))

print(f"  Identical pins: {len(identical_pins)}")
print(f"  Different pins: {len(different_pins)}")

# 显示一些不同的示例
if different_pins:
    print("\n[Step 4] Sample pins with different values across corners:")
    for pin_name, caps in different_pins[:10]:
        print(f"\n  {pin_name}:")
        for corner, cap in caps.items():
            print(f"    {corner}: {cap}")

# 统计差异
if different_pins:
    print("\n[Step 5] Analyzing differences...")
    max_diff = 0
    total_diff = 0
    for pin_name, caps in different_pins:
        cap_list = list(caps.values())
        for i in range(len(cap_list)):
            for j in range(i+1, len(cap_list)):
                diff = sum(abs(a - b) for a, b in zip(cap_list[i], cap_list[j]))
                total_diff += diff
                max_diff = max(max_diff, diff)
    
    avg_diff = total_diff / (len(different_pins) * len(corners) * (len(corners)-1) / 2) if different_pins else 0
    print(f"  Average difference: {avg_diff:.6f}")
    print(f"  Maximum difference: {max_diff:.6f}")

# 结论
print("\n" + "=" * 60)
print("Conclusion:")
if len(different_pins) == 0:
    print("  ✅ 所有 corner 的 pin_cap 值完全相同！")
    print("  → 可以共享：同一 benchmark 的不同 corner 可以使用相同的 pin_cap.txt")
else:
    ratio = len(identical_pins) / len(all_pins) * 100
    print(f"  ⚠️  有 {len(different_pins)} 个 pin ({100-ratio:.1f}%) 在不同 corner 间有差异")
    print(f"  → 建议：")
    print(f"     - 如果差异很小（< 1%），可以共享")
    print(f"     - 如果差异较大，需要为每个 corner 保留独立的 pin_cap.txt")
    print(f"     - 或者按 (cell_type, pin_role) 建立映射表，按 corner 查询")

print("=" * 60)

