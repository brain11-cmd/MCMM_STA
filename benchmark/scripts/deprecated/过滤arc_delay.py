#!/usr/bin/env python3
"""
从 arc_delay.txt 生成 arc_delay.json，实现严格的重复边处理规则。

核心规则：
1. 边的唯一键：(src, dst, edge_type)
2. 选优策略：
   - 规则 A：优先保留"有效通道上非零最多"的
   - 规则 B：在 A 相同的情况下，选"有效通道延迟总量最大"的
   - 规则 C：如果全都是 0，保留第一条并标记为 all_zero_arc
3. 统计与报警：输出详细的处理统计和异常检测
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional
import csv


# ============================================================================
# 配置参数
# ============================================================================

EPS = 1e-12  # 非零判断阈值
CELL_ALL_ZERO_THRESHOLD = 0.05  # cell arcs 全 0 比例阈值（5%）


# ============================================================================
# 工具函数
# ============================================================================

def normalize_pin_name(pin_name: str) -> str:
    """规范化 pin_name"""
    return pin_name.strip()


def is_valid_pin_name(pin_name: str) -> bool:
    """
    判断是否为有效的 pin name。
    无效示例："_387_:" (没有 pin 名)
    """
    if not pin_name:
        return False
    # 如果包含 ':'，必须 ':' 后面有内容
    if ':' in pin_name:
        parts = pin_name.split(':', 1)
        if len(parts) < 2 or not parts[1]:
            return False
    return True


def parse_arc_delay_txt(txt_file: Path) -> List[Dict]:
    """
    解析 arc_delay.txt 文件。
    
    格式：From To Type dRR dRF dFR dFF mRR mRF mFR mFF
    
    返回：arc 记录列表
    """
    arcs = []
    
    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # 查找表头
    header_idx = -1
    for i, line in enumerate(lines):
        if 'From' in line and 'To' in line and 'Type' in line:
            header_idx = i
            break
    
    if header_idx == -1:
        raise ValueError(f"Could not find header in {txt_file}")
    
    # 解析数据行
    for line_num, line in enumerate(lines[header_idx + 2:], start=header_idx + 3):
        line = line.strip()
        if not line or line.startswith('-'):
            continue
        
        parts = line.split()
        if len(parts) < 11:
            continue
        
        from_pin = normalize_pin_name(parts[0])
        to_pin = normalize_pin_name(parts[1])
        arc_type_str = parts[2].lower()
        
        # 转换 edge_type: 'cell' -> 0, 'net' -> 1
        edge_type = 0 if arc_type_str == 'cell' else 1
        
        # 解析延迟值
        dRR = float(parts[3])
        dRF = float(parts[4])
        dFR = float(parts[5])
        dFF = float(parts[6])
        
        # 解析 mask
        mRR = int(parts[7])
        mRF = int(parts[8])
        mFR = int(parts[9])
        mFF = int(parts[10])
        
        arcs.append({
            'src': from_pin,
            'dst': to_pin,
            'edge_type': edge_type,
            'dRR': dRR,
            'dRF': dRF,
            'dFR': dFR,
            'dFF': dFF,
            'mRR': mRR,
            'mRF': mRF,
            'mFR': mFR,
            'mFF': mFF,
            'line': line_num
        })
    
    return arcs


def load_graph_edges(edges_file: Path) -> Tuple[List[Dict], Dict[Tuple[str, str, int], int]]:
    """
    加载 graph_edges.csv，建立 (src, dst, edge_type) -> edge_id 的映射。
    
    返回：
        (edges_list, key_to_edge_id)
    """
    edges = []
    key_to_edge_id = {}
    
    if not edges_file.exists():
        print(f"  [WARNING] {edges_file} not found, will generate edge_id from arc_delay.txt")
        return edges, key_to_edge_id
    
    with open(edges_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            edge_id = int(row['edge_id'])
            src = normalize_pin_name(row['src'])
            dst = normalize_pin_name(row['dst'])
            edge_type = int(row.get('edge_type', 0))
            
            key = (src, dst, edge_type)
            key_to_edge_id[key] = edge_id
            
            edges.append({
                'edge_id': edge_id,
                'src': src,
                'dst': dst,
                'edge_type': edge_type
            })
    
    return edges, key_to_edge_id


# ============================================================================
# 核心选优规则
# ============================================================================

def compute_valid_nonzero_count(arc: Dict) -> int:
    """
    计算有效通道上非零延迟的数量。
    只统计 mask=1 且 delay > EPS 的通道。
    """
    count = 0
    if arc['mRR'] == 1 and abs(arc['dRR']) > EPS:
        count += 1
    if arc['mRF'] == 1 and abs(arc['dRF']) > EPS:
        count += 1
    if arc['mFR'] == 1 and abs(arc['dFR']) > EPS:
        count += 1
    if arc['mFF'] == 1 and abs(arc['dFF']) > EPS:
        count += 1
    return count


def compute_sum_delay(arc: Dict) -> float:
    """
    计算有效通道的延迟总量。
    只统计 mask=1 的通道的延迟绝对值之和。
    """
    total = 0.0
    if arc['mRR'] == 1:
        total += abs(arc['dRR'])
    if arc['mRF'] == 1:
        total += abs(arc['dRF'])
    if arc['mFR'] == 1:
        total += abs(arc['dFR'])
    if arc['mFF'] == 1:
        total += abs(arc['dFF'])
    return total


def is_all_zero_placeholder(arc: Dict) -> bool:
    """
    判断是否为全 0 占位符。
    条件：所有 mask=1 的通道延迟都是 0。
    """
    if arc['mRR'] == 1 and abs(arc['dRR']) > EPS:
        return False
    if arc['mRF'] == 1 and abs(arc['dRF']) > EPS:
        return False
    if arc['mFR'] == 1 and abs(arc['dFR']) > EPS:
        return False
    if arc['mFF'] == 1 and abs(arc['dFF']) > EPS:
        return False
    return True


def select_best_arc(candidates: List[Dict]) -> Tuple[Dict, str]:
    """
    从候选 arcs 中选择最优的一条。
    
    规则：
    - 规则 A：优先选择 valid_nonzero_count 最大的
    - 规则 B：在 A 相同的情况下，选择 sum_delay 最大的
    - 规则 C：如果全都是 0，保留第一条并标记为 all_zero_arc
    
    返回：
        (selected_arc, reason)
    """
    if not candidates:
        raise ValueError("Empty candidates list")
    
    # 计算每个候选的指标
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
    
    # 如果最大 nonzero_count 为 0，说明全是占位符（规则 C）
    if max_nonzero == 0:
        return scored[0]['arc'], 'all_zero_arc'
    
    # 规则 A：筛选出 nonzero_count 最大的
    top_nonzero = [s for s in scored if s['nonzero_count'] == max_nonzero]
    
    # 规则 B：在 top_nonzero 中按 sum_delay 降序
    top_nonzero.sort(key=lambda x: x['sum_delay'], reverse=True)
    
    selected = top_nonzero[0]
    
    # 判断原因
    if len(top_nonzero) > 1:
        reason = f"selected_by_rule_A_B (nonzero={max_nonzero}, sum={selected['sum_delay']:.6f})"
    else:
        reason = f"selected_by_rule_A (nonzero={max_nonzero})"
    
    return selected['arc'], reason


# ============================================================================
# 主处理流程
# ============================================================================

def process_arc_delay(
    txt_file: Path,
    edges_file: Optional[Path],
    output_file: Path,
    corner: str = "unknown",
    time_unit: str = "ns"
) -> Dict:
    """
    处理 arc_delay.txt，生成 arc_delay.json。
    
    返回：统计信息字典
    """
    print("=" * 60)
    print("Processing arc_delay.txt with Canonicalization Rules")
    print("=" * 60)
    
    # 1. 解析 arc_delay.txt
    print(f"\n[Step 1] Parsing {txt_file.name}...")
    raw_arcs = parse_arc_delay_txt(txt_file)
    print(f"  Total raw arcs: {len(raw_arcs)}")
    
    # 2. 加载 graph_edges（如果存在）
    print(f"\n[Step 2] Loading graph edges...")
    edges_list, key_to_edge_id = load_graph_edges(edges_file) if edges_file else ([], {})
    if edges_list:
        print(f"  Loaded {len(edges_list)} edges from {edges_file.name}")
    else:
        print(f"  No graph_edges.csv found, will generate edge_id from arc_delay.txt")
    
    # 3. 过滤无效 pin name
    print(f"\n[Step 3] Filtering invalid pin names...")
    valid_arcs = []
    invalid_count = 0
    for arc in raw_arcs:
        if is_valid_pin_name(arc['src']) and is_valid_pin_name(arc['dst']):
            valid_arcs.append(arc)
        else:
            invalid_count += 1
    
    print(f"  Valid arcs: {len(valid_arcs)}")
    print(f"  Invalid arcs (dropped): {invalid_count}")
    
    # 4. 按 (src, dst, edge_type) 分组
    print(f"\n[Step 4] Grouping arcs by (src, dst, edge_type)...")
    groups = defaultdict(list)
    for arc in valid_arcs:
        key = (arc['src'], arc['dst'], arc['edge_type'])
        groups[key].append(arc)
    
    num_groups = len(groups)
    num_groups_with_conflict = sum(1 for v in groups.values() if len(v) > 1)
    
    print(f"  Unique edge groups: {num_groups}")
    print(f"  Groups with conflicts (>1 candidate): {num_groups_with_conflict}")
    
    # 5. 对每组应用选优规则
    print(f"\n[Step 5] Applying selection rules (A/B/C)...")
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
        
        # 如果只有一条，直接选择
        if len(candidates) == 1:
            selected = candidates[0]
            reason = 'single_candidate'
        else:
            # 多条候选，应用选优规则
            selected, reason = select_best_arc(candidates)
            stats['num_conflict_groups'] += 1
            
            # 记录冲突详情（前 10 个）
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
            if edge_type == 0:  # cell
                stats['cell_all_zero_count'] += 1
            else:  # net
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
    
    # 6. 分配 edge_id 并生成 JSON
    print(f"\n[Step 6] Assigning edge_id and generating JSON...")
    
    # 如果已有 graph_edges，使用其 edge_id；否则按顺序分配
    if key_to_edge_id:
        # 使用 graph_edges 的 edge_id
        missing_keys = []
        for key, arc in selected_arcs:
            if key not in key_to_edge_id:
                missing_keys.append(key)
        
        if missing_keys:
            print(f"  [WARNING] {len(missing_keys)} selected arcs not in graph_edges.csv")
            # 为缺失的分配新的 edge_id
            max_id = max(key_to_edge_id.values()) if key_to_edge_id else -1
            for key in missing_keys:
                max_id += 1
                key_to_edge_id[key] = max_id
    else:
        # 没有 graph_edges，按顺序分配
        for idx, (key, _) in enumerate(selected_arcs):
            if key not in key_to_edge_id:
                key_to_edge_id[key] = idx
    
    # 生成 JSON 结构
    arcs_json = []
    for key, arc in selected_arcs:
        edge_id = key_to_edge_id[key]
        
        arc_json = {
            'edge_id': edge_id,
            'src': arc['src'],
            'dst': arc['dst'],
            'edge_type': arc['edge_type'],
            'delay': {
                'dRR': arc['dRR'],
                'dRF': arc['dRF'],
                'dFR': arc['dFR'],
                'dFF': arc['dFF']
            },
            'mask': {
                'maskRR': arc['mRR'],
                'maskRF': arc['mRF'],
                'maskFR': arc['mFR'],
                'maskFF': arc['mFF']
            }
        }
        arcs_json.append(arc_json)
    
    # 按 edge_id 排序
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
    
    # 7. 计算统计信息
    total_cell = sum(1 for _, arc in selected_arcs if arc['edge_type'] == 0)
    total_net = sum(1 for _, arc in selected_arcs if arc['edge_type'] == 1)
    
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
    print(f"  Raw arcs from txt: {summary['num_raw_arcs']}")
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
        print(f"            Possible issues: no update_timing, library not loaded, wrong corner")
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


def save_meta(summary: Dict, meta_file: Path):
    """保存元数据到 JSON"""
    meta = {
        'processing_summary': summary,
        'rules': {
            'edge_key': '(src, dst, edge_type)',
            'selection_rule_A': 'Select arc with largest valid_nonzero_count',
            'selection_rule_B': 'If tie in A, select arc with largest sum_delay',
            'selection_rule_C': 'If all zero, keep first and mark as all_zero_arc',
            'eps': EPS,
            'cell_all_zero_threshold': CELL_ALL_ZERO_THRESHOLD
        }
    }
    
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    
    print(f"\n  Saved metadata to {meta_file.name}")


# ============================================================================
# Main
# ============================================================================

def main():
    if len(sys.argv) < 3:
        print("Usage: python fill_arc_delay_from_txt.py <arc_delay.txt> <output.json> [options]")
        print("  Options:")
        print("    --edges <graph_edges.csv>  : Graph edges file (for edge_id alignment)")
        print("    --corner <corner_name>     : Corner name (default: unknown)")
        print("    --time-unit <unit>         : Time unit (default: ns)")
        print("    --meta <meta.json>         : Output metadata file")
        sys.exit(1)
    
    txt_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    # 解析选项
    edges_file = None
    corner = "unknown"
    time_unit = "ns"
    meta_file = None
    
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == '--edges' and i + 1 < len(sys.argv):
            edges_file = Path(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--corner' and i + 1 < len(sys.argv):
            corner = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--time-unit' and i + 1 < len(sys.argv):
            time_unit = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--meta' and i + 1 < len(sys.argv):
            meta_file = Path(sys.argv[i + 1])
            i += 2
        else:
            i += 1
    
    if not txt_file.exists():
        print(f"Error: {txt_file} not found")
        sys.exit(1)
    
    # 处理
    summary = process_arc_delay(txt_file, edges_file, output_file, corner, time_unit)
    
    # 打印摘要
    print_summary(summary)
    
    # 保存元数据
    if meta_file:
        save_meta(summary, meta_file)
    
    print("\n[OK] Processing complete!")


if __name__ == "__main__":
    main()
