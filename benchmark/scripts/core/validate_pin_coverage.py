#!/usr/bin/env python3
"""
三步自检：验证pin coverage是否正常
1. 用pin-only集合重新算coverage
2. 检查缺失的那部分pin类型
3. 传播可达性验证
"""

import sys
from pathlib import Path
import re
from collections import defaultdict

def parse_pin_static(pin_static_file: Path):
    """解析pin_static.txt，提取pin信息"""
    pins = {}
    with open(pin_static_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 跳过header
    header_found = False
    for line in lines:
        if 'Pin' in line and 'Role' in line:
            header_found = True
            continue
        if not header_found or not line.strip() or line.strip().startswith('-'):
            continue
        
        parts = line.split()
        if len(parts) < 2:
            continue
        
        # 格式: Pin Fanin Fanout CellType PinRole
        # 例如: "  _387_:CLK           3           5           DFFX1_RVT         CLK"
        pin_name = parts[0]  # Pin name在第一个字段
        # PinRole在最后一个字段
        role = parts[-1] if len(parts) > 1 else None
        
        pins[pin_name] = {
            'name': pin_name,
            'role': role,
            'raw_line': line.strip()
        }
    
    return pins

def parse_arrival(arrival_file: Path):
    """解析arrival.txt，提取有arrival的pins"""
    pins_in_arrival = set()
    with open(arrival_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 跳过header
    header_found = False
    for line in lines:
        if 'Pin' in line and ('E/R' in line or 'L/R' in line):
            header_found = True
            continue
        if not header_found or not line.strip() or line.strip().startswith('-'):
            continue
        
        parts = line.split()
        if len(parts) < 5:
            continue
        
        pin_name = parts[-1]  # Pin name在最后
        if pin_name and pin_name != 'n/a':
            pins_in_arrival.add(pin_name)
    
    return pins_in_arrival

def get_pin_only_nodes(pins: dict):
    """
    获取pin-only节点集合
    pin_only_nodes = 所有形如"_123_:A1" 或有 pin_role 的节点
    去掉_123_: (INSTANCE)以及任何无 pin_role 的节点
    """
    pin_only = set()
    
    for pin_name, pin_info in pins.items():
        # 排除形如"_123_:"的INSTANCE节点（没有冒号后的pin名）
        if pin_name.endswith(':'):
            continue
        
        # 检查是否有pin_role（且不是N/A）
        has_role = pin_info.get('role') is not None and pin_info.get('role') != 'N/A'
        
        # 检查是否形如"_123_:A1"（包含冒号，后面有pin名）
        has_colon_format = ':' in pin_name and not pin_name.endswith(':')
        
        # 如果有role或符合pin格式，加入pin_only集合
        if has_role or has_colon_format:
            pin_only.add(pin_name)
    
    return pin_only

def categorize_missing_pins(missing_pins: set, pins: dict):
    """对缺失的pins进行分类"""
    categories = {
        'clock': [],
        'constant': [],
        'unconnected': [],
        'sequential_internal': [],
        'other': []
    }
    
    for pin_name in missing_pins:
        pin_info = pins.get(pin_name, {})
        role = pin_info.get('role', '')
        
        # 分类
        if 'clock' in role.lower() or 'clk' in pin_name.lower():
            categories['clock'].append(pin_name)
        elif 'constant' in role.lower() or 'vdd' in pin_name.lower() or 'vss' in pin_name.lower():
            categories['constant'].append(pin_name)
        elif 'unconnected' in role.lower() or 'nc' in pin_name.lower():
            categories['unconnected'].append(pin_name)
        elif 'internal' in role.lower() and ('ff' in pin_name.lower() or 'latch' in pin_name.lower()):
            categories['sequential_internal'].append(pin_name)
        else:
            categories['other'].append(pin_name)
    
    return categories

def analyze_corner(corner_dir: Path):
    """分析单个corner的pin coverage"""
    print("=" * 80)
    print(f"Analyzing: {corner_dir.name}")
    print("=" * 80)
    
    pin_static_file = corner_dir / "pin_static.txt"
    arrival_file = corner_dir / "arrival.txt"
    
    if not pin_static_file.exists():
        print(f"[ERROR] pin_static.txt not found")
        return
    if not arrival_file.exists():
        print(f"[ERROR] arrival.txt not found")
        return
    
    # 解析文件
    print("\n[Step 0] Parsing files...")
    pins = parse_pin_static(pin_static_file)
    pins_in_arrival = parse_arrival(arrival_file)
    
    print(f"  Total pins in pin_static: {len(pins)}")
    print(f"  Pins in arrival: {len(pins_in_arrival)}")
    
    # Step 1: 用pin-only集合重新算coverage
    print("\n" + "=" * 80)
    print("[Step 1] 用pin-only集合重新算coverage (最关键)")
    print("=" * 80)
    
    pin_only_nodes = get_pin_only_nodes(pins)
    print(f"  pin_only_nodes count: {len(pin_only_nodes)}")
    
    # 计算intersection
    pins_in_arrival_pin_only = pins_in_arrival & pin_only_nodes
    coverage = len(pins_in_arrival_pin_only) / len(pin_only_nodes) if pin_only_nodes else 0.0
    
    print(f"  pins_in_arrival ∩ pin_only_nodes: {len(pins_in_arrival_pin_only)}")
    print(f"  Coverage = {len(pins_in_arrival_pin_only)} / {len(pin_only_nodes)} = {coverage:.4f} ({coverage*100:.2f}%)")
    
    if coverage >= 0.999:
        print(f"  [OK] Coverage接近100% (≥99.9%), 说明之前81%只是分母错了")
    else:
        print(f"  [WARNING] Coverage {coverage*100:.2f}% < 99.9%")
    
    # Step 2: 检查缺失的那部分pin类型
    print("\n" + "=" * 80)
    print("[Step 2] 检查缺失的那部分pin类型")
    print("=" * 80)
    
    missing_pins = pin_only_nodes - pins_in_arrival
    print(f"  missing_pins = pin_only_nodes - pins_in_arrival: {len(missing_pins)} pins")
    
    if missing_pins:
        categories = categorize_missing_pins(missing_pins, pins)
        
        print(f"\n  分类统计:")
        for cat, pin_list in categories.items():
            if pin_list:
                print(f"    {cat}: {len(pin_list)} pins")
                if len(pin_list) <= 10:
                    for pin in pin_list[:5]:
                        print(f"      - {pin}")
                    if len(pin_list) > 5:
                        print(f"      ... and {len(pin_list) - 5} more")
        
        # 判断是否正常
        total_acceptable = (len(categories['clock']) + 
                          len(categories['constant']) + 
                          len(categories['unconnected']) + 
                          len(categories['sequential_internal']))
        acceptable_ratio = total_acceptable / len(missing_pins) if missing_pins else 0.0
        
        print(f"\n  可接受的缺失pins (clock/constant/unconnected/sequential_internal): {total_acceptable}/{len(missing_pins)} ({acceptable_ratio*100:.2f}%)")
        
        if acceptable_ratio >= 0.8:
            print(f"  [OK] 缺失主要是不可达/无意义节点,可接受")
        else:
            print(f"  [WARNING] 缺失分布可能有问题,需要进一步检查")
    else:
        print(f"  [OK] 没有缺失pins")
    
    # Step 3: 传播可达性验证
    print("\n" + "=" * 80)
    print("[Step 3] 传播可达性验证 (与STA传播直接相关)")
    print("=" * 80)
    
    # 需要读取graph_edges.csv来构建图
    graph_edges_file = corner_dir.parent.parent / "static" / "graph_edges.csv"
    if not graph_edges_file.exists():
        # 尝试在当前目录
        graph_edges_file = corner_dir / "graph_edges.csv"
    
    if graph_edges_file.exists():
        print(f"  Reading graph from: {graph_edges_file}")
        # 构建图
        graph = defaultdict(set)  # src -> {dst1, dst2, ...}
        with open(graph_edges_file, 'r', encoding='utf-8') as f:
            import csv
            reader = csv.DictReader(f)
            for row in reader:
                src = row.get('src', '').strip()
                dst = row.get('dst', '').strip()
                if src and dst:
                    graph[src].add(dst)
        
        print(f"  Graph has {len(graph)} nodes with outgoing edges")
        
        # 找到startpoints (PI + clock launch pins)
        startpoints = set()
        for pin_name in pin_only_nodes:
            pin_info = pins.get(pin_name, {})
            role = pin_info.get('role', '')
            # PI (primary input) 或 clock
            if 'input' in role.lower() or 'clock' in role.lower() or 'clk' in pin_name.lower():
                startpoints.add(pin_name)
        
        print(f"  Startpoints (PI + clock): {len(startpoints)}")
        
        # BFS从startpoints遍历
        visited = set()
        queue = list(startpoints)
        for sp in startpoints:
            visited.add(sp)
        
        while queue:
            current = queue.pop(0)
            for neighbor in graph.get(current, set()):
                if neighbor not in visited and neighbor in pin_only_nodes:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        # 找到endpoints (FEP - flip-flop endpoints)
        # Endpoints应该是输出pin或flip-flop的Q/QN，但不包括PI
        endpoints = set()
        for pin_name in pin_only_nodes:
            pin_info = pins.get(pin_name, {})
            role = pin_info.get('role', '')
            
            # 排除PI（Primary Input）
            if role == 'PI' or 'input' in role.lower():
                continue
            
            # 输出pin或flip-flop相关（Q/QN）
            if role in ['Q', 'QN'] or 'q' in pin_name.lower():
                endpoints.add(pin_name)
        
        print(f"  Endpoints (FEP): {len(endpoints)}")
        
        # 检查endpoint可达性
        reachable_endpoints = endpoints & visited
        unreachable_endpoints = endpoints - visited
        endpoint_coverage = len(reachable_endpoints) / len(endpoints) if endpoints else 0.0
        
        print(f"  Reachable endpoints: {len(reachable_endpoints)}/{len(endpoints)} ({endpoint_coverage*100:.2f}%)")
        
        if unreachable_endpoints:
            print(f"\n  Unreachable endpoints ({len(unreachable_endpoints)}):")
            # 分析不可达endpoints的类型
            unreachable_by_role = defaultdict(list)
            for ep in list(unreachable_endpoints)[:20]:  # 只显示前20个
                pin_info = pins.get(ep, {})
                role = pin_info.get('role', 'N/A')
                unreachable_by_role[role].append(ep)
            
            for role, ep_list in unreachable_by_role.items():
                print(f"    {role}: {len(ep_list)} endpoints")
                if len(ep_list) <= 5:
                    for ep in ep_list:
                        print(f"      - {ep}")
            
            if len(unreachable_endpoints) > 20:
                print(f"    ... and {len(unreachable_endpoints) - 20} more")
        
        if endpoint_coverage >= 0.999:
            print(f"  [OK] Endpoint可达性100%, 中间少量pin缺arrival可通过传播计算")
        else:
            print(f"  [WARNING] Endpoint可达性 {endpoint_coverage*100:.2f}% < 100%")
            print(f"  [INFO] 如果不可达endpoints主要是QN（反相输出）或内部节点，可能可接受")
    else:
        print(f"  [WARNING] graph_edges.csv not found, skipping reachability check")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_pin_coverage.py <corner_dir>")
        sys.exit(1)
    
    corner_dir = Path(sys.argv[1])
    if not corner_dir.exists():
        print(f"[ERROR] Directory not found: {corner_dir}")
        sys.exit(1)
    
    analyze_corner(corner_dir)

