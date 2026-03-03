#!/usr/bin/env python3
"""
直接处理现有的 arc_delay.json，应用去重规则并重新生成。

核心规则：
1. 边的唯一键：(src, dst, edge_type)
2. 选优策略：
   - 规则 A：优先保留"有效通道上非零最多"的
   - 规则 B：在 A 相同的情况下，选"有效通道延迟总量最大"的
   - 规则 C：如果全都是 0，保留第一条并标记为 all_zero_arc
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

EPS = 1e-12
CELL_ALL_ZERO_THRESHOLD = 0.05


def normalize_pin_name(pin_name: str) -> str:
    """规范化 pin_name"""
    return pin_name.strip()


def is_valid_pin_name(pin_name: str) -> bool:
    """判断是否为有效的 pin name"""
    if not pin_name:
        return False
    if ':' in pin_name:
        parts = pin_name.split(':', 1)
        if len(parts) < 2 or not parts[1]:
            return False
    return True


def compute_valid_nonzero_count(arc: Dict) -> int:
    """计算有效通道上非零延迟的数量"""
    delay = arc.get('delay', {})
    mask = arc.get('mask', {})
    count = 0
    if mask.get('maskRR', 0) == 1 and abs(delay.get('dRR', 0)) > EPS:
        count += 1
    if mask.get('maskRF', 0) == 1 and abs(delay.get('dRF', 0)) > EPS:
        count += 1
    if mask.get('maskFR', 0) == 1 and abs(delay.get('dFR', 0)) > EPS:
        count += 1
    if mask.get('maskFF', 0) == 1 and abs(delay.get('dFF', 0)) > EPS:
        count += 1
    return count


def compute_sum_delay(arc: Dict) -> float:
    """计算有效通道的延迟总量"""
    delay = arc.get('delay', {})
    mask = arc.get('mask', {})
    total = 0.0
    if mask.get('maskRR', 0) == 1:
        total += abs(delay.get('dRR', 0))
    if mask.get('maskRF', 0) == 1:
        total += abs(delay.get('dRF', 0))
    if mask.get('maskFR', 0) == 1:
        total += abs(delay.get('dFR', 0))
    if mask.get('maskFF', 0) == 1:
        total += abs(delay.get('dFF', 0))
    return total


def is_all_zero_placeholder(arc: Dict) -> bool:
    """判断是否为全 0 占位符"""
    delay = arc.get('delay', {})
    mask = arc.get('mask', {})
    if mask.get('maskRR', 0) == 1 and abs(delay.get('dRR', 0)) > EPS:
        return False
    if mask.get('maskRF', 0) == 1 and abs(delay.get('dRF', 0)) > EPS:
        return False
    if mask.get('maskFR', 0) == 1 and abs(delay.get('dFR', 0)) > EPS:
        return False
    if mask.get('maskFF', 0) == 1 and abs(delay.get('dFF', 0)) > EPS:
        return False
    return True


def select_best_arc(candidates: List[Dict]) -> Tuple[Dict, str]:
    """从候选 arcs 中选择最优的一条"""
    if not candidates:
        raise ValueError("Empty candidates list")
    
    scored = []
    for arc in candidates:
        nonzero_count = compute_valid_nonzero_count(arc)
        sum_delay = compute_sum_delay(arc)
        is_placeholder = is_all_zero_placeholder(arc)
        
        scored.append({
            'arc': arc,
            'nonzero_count': nonzero_count,
            'sum_delay': sum_delay,
            'is_placeholder': is_placeholder
        })
    
    # 规则 A：按 nonzero_count 降序
    scored.sort(key=lambda x: x['nonzero_count'], reverse=True)
    max_nonzero = scored[0]['nonzero_count']
    
    # 规则 C：如果最大 nonzero_count 为 0，说明全是占位符
    if max_nonzero == 0:
        return scored[0]['arc'], 'all_zero_arc'
    
    # 规则 A：筛选出 nonzero_count 最大的
    top_nonzero = [s for s in scored if s['nonzero_count'] == max_nonzero]
    
    # 规则 B：在 top_nonzero 中按 sum_delay 降序
    top_nonzero.sort(key=lambda x: x['sum_delay'], reverse=True)
    
    selected = top_nonzero[0]
    
    if len(top_nonzero) > 1:
        reason = f"selected_by_rule_A_B (nonzero={max_nonzero}, sum={selected['sum_delay']:.6f})"
    else:
        reason = f"selected_by_rule_A (nonzero={max_nonzero})"
    
    return selected['arc'], reason


def canonicalize_arc_delay_json(input_file: Path, output_file: Path) -> Dict:
    """处理 arc_delay.json，去重并重新生成"""
    print("=" * 60)
    print("Canonicalizing arc_delay.json")
    print("=" * 60)
    
    # 读取现有 JSON
    print(f"\n[Step 1] Reading {input_file.name}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    corner = data.get('corner', 'unknown')
    time_unit = data.get('time_unit', 'ns')
    raw_arcs = data.get('arcs', [])
    
    print(f"  Total arcs: {len(raw_arcs)}")
    
    # 过滤无效 pin name
    print(f"\n[Step 2] Filtering invalid pin names...")
    valid_arcs = []
    invalid_count = 0
    for arc in raw_arcs:
        src = normalize_pin_name(arc.get('src', ''))
        dst = normalize_pin_name(arc.get('dst', ''))
        if is_valid_pin_name(src) and is_valid_pin_name(dst):
            valid_arcs.append(arc)
        else:
            invalid_count += 1
    
    print(f"  Valid arcs: {len(valid_arcs)}")
    print(f"  Invalid arcs (dropped): {invalid_count}")
    
    # 按 (src, dst, edge_type) 分组
    print(f"\n[Step 3] Grouping arcs by (src, dst, edge_type)...")
    groups = defaultdict(list)
    for arc in valid_arcs:
        src = normalize_pin_name(arc.get('src', ''))
        dst = normalize_pin_name(arc.get('dst', ''))
        edge_type = arc.get('edge_type', 0)
        key = (src, dst, edge_type)
        groups[key].append(arc)
    
    num_groups = len(groups)
    num_groups_with_conflict = sum(1 for v in groups.values() if len(v) > 1)
    
    print(f"  Unique edge groups: {num_groups}")
    print(f"  Groups with conflicts (>1 candidate): {num_groups_with_conflict}")
    
    # 对每组应用选优规则
    print(f"\n[Step 4] Applying selection rules (A/B/C)...")
    selected_arcs = []
    stats = {
        'num_placeholder_dropped': 0,
        'num_all_zero_groups': 0,
        'num_conflict_groups': 0,
        'conflict_details': [],
        'cell_all_zero_count': 0,
        'net_all_zero_count': 0
    }
    
    for key, candidates in groups.items():
        src, dst, edge_type = key
        
        if len(candidates) == 1:
            selected = candidates[0]
            reason = 'single_candidate'
        else:
            selected, reason = select_best_arc(candidates)
            stats['num_conflict_groups'] += 1
            
            if len(stats['conflict_details']) < 10:
                stats['conflict_details'].append({
                    'src': src,
                    'dst': dst,
                    'edge_type': edge_type,
                    'num_candidates': len(candidates),
                    'selected_reason': reason
                })
        
        # 检查是否为全 0
        if is_all_zero_placeholder(selected):
            stats['num_all_zero_groups'] += 1
            if edge_type == 0:
                stats['cell_all_zero_count'] += 1
            else:
                stats['net_all_zero_count'] += 1
        
        # 检查是否有被丢弃的占位符
        if len(candidates) > 1:
            for cand in candidates:
                if cand != selected and is_all_zero_placeholder(cand):
                    stats['num_placeholder_dropped'] += 1
        
        selected_arcs.append((key, selected))
    
    print(f"  Selected arcs: {len(selected_arcs)}")
    print(f"  All-zero groups: {stats['num_all_zero_groups']}")
    print(f"  Placeholder arcs dropped: {stats['num_placeholder_dropped']}")
    
    # 重新分配 edge_id 并生成 JSON
    print(f"\n[Step 5] Reassigning edge_id and generating JSON...")
    
    arcs_json = []
    for idx, (key, arc) in enumerate(selected_arcs):
        # 创建新的 arc 对象，更新 edge_id
        new_arc = {
            'edge_id': idx,
            'src': arc['src'],
            'dst': arc['dst'],
            'edge_type': arc['edge_type'],
            'delay': arc.get('delay', {}),
            'mask': arc.get('mask', {})
        }
        arcs_json.append(new_arc)
    
    # 按 edge_id 排序（应该已经是顺序的）
    arcs_json.sort(key=lambda x: x['edge_id'])
    
    # 写入 JSON
    output_data = {
        'corner': corner,
        'time_unit': time_unit,
        'arcs': arcs_json
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"  Wrote {len(arcs_json)} arcs to {output_file.name}")
    
    # 计算统计信息
    total_cell = sum(1 for _, arc in selected_arcs if arc.get('edge_type', 0) == 0)
    total_net = sum(1 for _, arc in selected_arcs if arc.get('edge_type', 0) == 1)
    
    cell_all_zero_ratio = stats['cell_all_zero_count'] / total_cell if total_cell > 0 else 0.0
    net_all_zero_ratio = stats['net_all_zero_count'] / total_net if total_net > 0 else 0.0
    
    summary = {
        'num_raw_arcs': len(raw_arcs),
        'num_invalid_pin_dropped': invalid_count,
        'num_groups': num_groups,
        'num_groups_with_conflict': num_groups_with_conflict,
        'num_placeholder_dropped': stats['num_placeholder_dropped'],
        'num_all_zero_groups': stats['num_all_zero_groups'],
        'num_conflict_groups': stats['num_conflict_groups'],
        'cell_all_zero_count': stats['cell_all_zero_count'],
        'net_all_zero_count': stats['net_all_zero_count'],
        'total_cell_arcs': total_cell,
        'total_net_arcs': total_net,
        'cell_all_zero_ratio': cell_all_zero_ratio,
        'net_all_zero_ratio': net_all_zero_ratio,
        'conflict_details': stats['conflict_details']
    }
    
    return summary


def print_summary(summary: Dict):
    """打印统计摘要"""
    print("\n" + "=" * 60)
    print("Processing Summary")
    print("=" * 60)
    
    print(f"\nInput Statistics:")
    print(f"  Raw arcs: {summary['num_raw_arcs']}")
    print(f"  Invalid pin names (dropped): {summary['num_invalid_pin_dropped']}")
    
    print(f"\nGrouping Statistics:")
    print(f"  Unique edge groups: {summary['num_groups']}")
    print(f"  Groups with conflicts: {summary['num_groups_with_conflict']}")
    
    print(f"\nSelection Statistics:")
    print(f"  Placeholder arcs dropped: {summary['num_placeholder_dropped']}")
    print(f"  All-zero groups: {summary['num_all_zero_groups']}")
    
    print(f"\nAll-Zero Analysis:")
    print(f"  Cell arcs - all zero: {summary['cell_all_zero_count']}/{summary['total_cell_arcs']} "
          f"({summary['cell_all_zero_ratio']*100:.2f}%)")
    print(f"  Net arcs - all zero: {summary['net_all_zero_count']}/{summary['total_net_arcs']} "
          f"({summary['net_all_zero_ratio']*100:.2f}%)")
    
    # 报警检查
    print(f"\nValidation:")
    cell_warning = summary['cell_all_zero_ratio'] > CELL_ALL_ZERO_THRESHOLD
    if cell_warning:
        print(f"  [WARNING] Cell all-zero ratio ({summary['cell_all_zero_ratio']*100:.2f}%) "
              f"exceeds threshold ({CELL_ALL_ZERO_THRESHOLD*100:.0f}%)")
    else:
        print(f"  [OK] Cell all-zero ratio ({summary['cell_all_zero_ratio']*100:.2f}%) "
              f"within threshold ({CELL_ALL_ZERO_THRESHOLD*100:.0f}%)")
    
    if summary['num_conflict_groups'] > 0:
        print(f"  [INFO] {summary['num_conflict_groups']} groups had conflicts resolved by rules A/B")
        if summary['conflict_details']:
            print(f"  Sample conflicts (first 3):")
            for detail in summary['conflict_details'][:3]:
                print(f"    {detail['src']} -> {detail['dst']} (type={detail['edge_type']}, "
                      f"candidates={detail['num_candidates']}, reason={detail['selected_reason']})")
    
    print("\n" + "=" * 60)


def main():
    if len(sys.argv) < 2:
        print("Usage: python canonicalize_arc_delay_json.py <arc_delay.json> [output.json]")
        print("  If output.json is not specified, will overwrite input file")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        output_file = Path(sys.argv[2])
    else:
        # 如果没有指定输出，备份原文件并覆盖
        backup_file = input_file.with_suffix('.json.backup')
        print(f"  Creating backup: {backup_file.name}")
        import shutil
        shutil.copy2(input_file, backup_file)
        output_file = input_file
    
    if not input_file.exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)
    
    # 处理
    summary = canonicalize_arc_delay_json(input_file, output_file)
    
    # 打印摘要
    print_summary(summary)
    
    print("\n[OK] Processing complete!")


if __name__ == "__main__":
    main()






















