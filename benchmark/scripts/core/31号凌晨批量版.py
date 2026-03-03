#!/usr/bin/env python3
"""
通用数据导出与标准化脚本

支持12个benchmark和27个corners的数据导出、清洗和标准化。

核心功能：
1. Step1: 运行OpenTimer导出原始dump
2. Step2: 解析+清洗（过滤/去重/对齐edge_id）
3. Step3: 写标准化文件+校验+meta.json

满足所有A-I要求：
A. 输入一致性与版本控制
B. 权威结构定义（graph_edges.csv唯一）
C. 节点集合与过滤规则
D. 重复边与占位符处理
E. Net arc的通道与mask规则
F. Corner输出文件规范
G. 必做校验
H. 训练样本生成
I. 通用参数化设计
"""

import json
import csv
import hashlib
import subprocess
import time
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, field
import argparse

# ============================================================================
# 常量定义
# ============================================================================

EPS = 1e-12
CELL_ALL_ZERO_THRESHOLD = 0.05
PIN_COVERAGE_THRESHOLD = 0.999  # ≥99.9%
EDGE_COVERAGE_THRESHOLD = 0.999  # ≥99.9%

# 所有benchmarks
ALL_BENCHMARKS = [
    'aes', 'chameleon', 'dynamic_node', 'ethmac', 'fifo', 'gcd',
    'jpeg', 'mock-alu', 'riscv32i', 'spi', 'tinyRocket', 'uart'
]

# 所有corners（27个）
ALL_CORNERS = [
    # FF (9个)
    'ff0p85vn40c', 'ff0p85v25c', 'ff0p85v125c',
    'ff0p95vn40c', 'ff0p95v25c', 'ff0p95v125c',
    'ff1p16vn40c', 'ff1p16v25c', 'ff1p16v125c',
    # SS (9个)
    'ss0p7vn40c', 'ss0p7v25c', 'ss0p7v125c',
    'ss0p75vn40c', 'ss0p75v25c', 'ss0p75v125c',
    'ss0p95vn40c', 'ss0p95v25c', 'ss0p95v125c',
    # TT (9个)
    'tt0p78vn40c', 'tt0p78v25c', 'tt0p78v125c',
    'tt0p85vn40c', 'tt0p85v25c', 'tt0p85v125c',
    'tt1p05vn40c', 'tt1p05v25c', 'tt1p05v125c',
]

# Anchors (3个)
ANCHORS = [
    'ff1p16vn40c',  # A_fast
    'tt0p85v25c',   # A_typ
    'ss0p7v25c'     # A_slow
]

# Train Targets (15个: 其余所有 vn40c/25c)
TRAIN = [
    # FF (5个)
    'ff0p85vn40c', 'ff0p85v25c', 'ff0p95vn40c', 'ff1p16vn40c', 'ff1p16v25c',
    # SS (5个)
    'ss0p7vn40c', 'ss0p7v25c', 'ss0p75v25c', 'ss0p95vn40c', 'ss0p95v25c',
    # TT (5个)
    'tt0p78vn40c', 'tt0p78v25c', 'tt0p85vn40c', 'tt0p85v25c', 'tt1p05vn40c'
]

# Val Targets (3个: 从 vn40c/25c 里抽，覆盖 ff/ss/tt)
VAL = [
    'ff0p95v25c',
    'ss0p75vn40c',
    'tt1p05v25c'
]

# Test Targets (9个: 全部 125°C)
TEST = [
    'ff0p85v125c', 'ff0p95v125c', 'ff1p16v125c',
    'ss0p7v125c', 'ss0p75v125c', 'ss0p95v125c',
    'tt0p78v125c', 'tt0p85v125c', 'tt1p05v125c'
]

# Targets（排除anchors，用于监督）
# anchors只做输入特征，不当监督target（避免trivial identity）
TRAIN_TARGETS = [c for c in TRAIN if c not in ANCHORS]
VAL_TARGETS = [c for c in VAL if c not in ANCHORS]
TEST_TARGETS = [c for c in TEST if c not in ANCHORS]


# ============================================================================
# 数据类定义
# ============================================================================

@dataclass
class Config:
    """配置参数"""
    benchmark: str
    corner: str
    benchmark_root: Path
    opentimer_path: Path
    lib_path_template: str  # 例如: "D:/bishe_database/BUFLIB/lib_rvt/saed32rvt_{corner}.lib"
    netlist_path_template: str  # 例如: "D:/bishe_database/benchmark/netlists/{benchmark}/{benchmark}_netlist.v"
    sdc_path_template: str  # 例如: "D:/bishe_database/benchmark/netlists/{benchmark}/{benchmark}.sdc"
    output_root: Path
    keep_pi_po: bool = True
    keep_instance: bool = False
    time_unit: str = "ns"
    opentimer_version: Optional[str] = None
    skip_opentimer: bool = False  # 跳过OpenTimer导出，直接使用现有数据
    existing_data_dir: Optional[Path] = None  # 现有数据目录（如果skip_opentimer=True）
    keep_tcl: bool = False  # 是否保留TCL文件（默认删除，debug时保留）


@dataclass
class ProcessingStats:
    """处理统计信息"""
    num_raw_arcs: int = 0
    num_invalid_pin_dropped: int = 0
    num_instance_filtered: int = 0
    num_groups: int = 0
    num_conflict_groups: int = 0
    num_placeholder_dropped: int = 0
    num_all_zero_groups: int = 0
    cell_all_zero_count: int = 0
    net_all_zero_count: int = 0
    total_cell_arcs: int = 0
    total_net_arcs: int = 0
    conflict_details: List[Dict] = field(default_factory=list)


# ============================================================================
# Pin Name规范化（全局唯一函数）
# ============================================================================

def normalize_pin_name(pin_name: str) -> str:
    """
    规范化pin name（全局唯一函数）
    
    规则：
    - 去引号、去转义
    - 保持大小写
    - 统一格式：Inst:Pin（如 _187_:A1）
    """
    if not pin_name:
        return ""
    
    # 去除首尾空白
    pin_name = pin_name.strip()
    
    # 去除引号（如果有）
    if pin_name.startswith('"') and pin_name.endswith('"'):
        pin_name = pin_name[1:-1]
    if pin_name.startswith("'") and pin_name.endswith("'"):
        pin_name = pin_name[1:-1]
    
    # 去转义（简单处理）
    pin_name = pin_name.replace('\\"', '"').replace("\\'", "'")
    
    # 保持大小写，统一格式为 Inst:Pin
    # 如果已经是 Inst:Pin 格式，直接返回
    # 如果是 Inst/Pin 格式，只替换最后一个/（实例/引脚分隔符）
    # 避免误替换实例层级中的/（如 top/u1/u2/A）
    if '/' in pin_name and ':' not in pin_name:
        inst, pin = pin_name.rsplit('/', 1)
        pin_name = inst + ':' + pin
    
    return pin_name


def is_valid_pin_name(pin_name: str) -> bool:
    """判断是否为有效的pin name"""
    if not pin_name:
        return False
    
    # 过滤无效pin name：例如 _387_: 这种没有pin名的边
    if ':' in pin_name:
        parts = pin_name.split(':', 1)
        if len(parts) < 2 or not parts[1]:
            return False
    
    return True


def is_instance_node(pin_name: str, pin_role: Optional[str] = None) -> bool:
    """
    判断是否为instance body节点
    
    修复：收紧判断规则，只匹配更确定的 instance body 形态，避免误删合法 pin 名
    
    规则（收紧版）：
    1. pin名以:结尾 → instance body（最确定）
    2. 冒号存在但后半为空（如 "_187_:"）→ instance body
    3. pin_role明确是INSTANCE/BODY → instance body
    4. 只匹配非常确定的 body pattern：_数字_: 或 _数字_（如 _123_:、_123_）
       不匹配 _123（可能是有 pin 的节点）
    """
    if not pin_name:
        return False
    
    # 规则1: pin名以:结尾 → instance body（最确定）
    if pin_name.endswith(':'):
        return True
    
    # 规则2: 冒号存在但后半为空也算 body（如 "_187_:"）
    if ':' in pin_name:
        parts = pin_name.split(':', 1)
        if len(parts) == 2 and not parts[1]:
            return True
    
    # 规则3: pin_role明确是INSTANCE/BODY → instance body
    if pin_role is not None:
        pr = str(pin_role).strip().upper()
        if pr in ("INSTANCE", "INST", "BODY", "CELL_BODY"):
            return True
    
    # 规则4: 只匹配非常确定的 body pattern（当pin_role缺失/无效时）
    # 修复：收紧到更确定的形态，避免误删合法的 _123 这种 pin 名
    # 只匹配：_数字_: 或 _数字_（如 _123_:、_123_）
    # 不匹配：_123（可能是有 pin 的节点）
    if pin_role is None or str(pin_role).strip().upper() in ("", "N/A", "NA", "NONE"):
        # 纯数字（可能是内部instance编号）
        if pin_name.isdigit():
            return True
        # 只匹配非常确定的 body pattern：_数字_: 或 _数字_（如 _123_:、_123_）
        # 不匹配 _123，避免误删合法的 pin 名
        if re.match(r'^_\d+_$', pin_name) or re.match(r'^_\d+_:$', pin_name):
            return True
    
    return False


# ============================================================================
# Arc处理函数
# ============================================================================

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
    """判断是否为全0占位符"""
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
    """
    从候选arcs中选择最优的一条（确定性规则）
    
    选优顺序：
    1. valid(mask=1)通道里非零数最多
    2. sum(delay)最大
    3. 仍相同则取第一条
    4. 全0的占位符优先丢弃
    """
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
    
    # 规则A：按nonzero_count降序
    scored.sort(key=lambda x: x['nonzero_count'], reverse=True)
    max_nonzero = scored[0]['nonzero_count']
    
    # 规则C：如果最大nonzero_count为0，说明全是占位符
    if max_nonzero == 0:
        return scored[0]['arc'], 'all_zero_arc'
    
    # 规则A：筛选出nonzero_count最大的
    top_nonzero = [s for s in scored if s['nonzero_count'] == max_nonzero]
    
    # 规则B：在top_nonzero中按sum_delay降序
    top_nonzero.sort(key=lambda x: x['sum_delay'], reverse=True)
    
    selected = top_nonzero[0]
    
    if len(top_nonzero) > 1:
        reason = f"selected_by_rule_A_B (nonzero={max_nonzero}, sum={selected['sum_delay']:.6f})"
    else:
        reason = f"selected_by_rule_A (nonzero={max_nonzero})"
    
    return selected['arc'], reason


def fix_net_arc_mask(arc: Dict) -> Dict:
    """
    修复Net arc的mask（固定规则）
    
    Net arc：固定mask=[1,0,0,1]（RF/FR永远无效，不算缺失）
    Cell arc：mask=[1,1,1,1]（若真缺失则对应通道置0）
    """
    edge_type = arc.get('edge_type', 0)
    mask = arc.get('mask', {}).copy()
    
    if edge_type == 1:  # Net arc
        # 固定mask=[1,0,0,1]
        mask['maskRR'] = 1
        mask['maskRF'] = 0
        mask['maskFR'] = 0
        mask['maskFF'] = 1
    
    arc['mask'] = mask
    return arc


# ============================================================================
# Step1: OpenTimer导出
# ============================================================================

def run_opentimer_export(config: Config) -> Dict[str, Path]:
    """
    运行OpenTimer导出原始dump
    
    返回导出的文件路径字典
    """
    print("=" * 60)
    print("Step 1: Running OpenTimer Export")
    print("=" * 60)
    
    # 构建路径
    lib_file = config.lib_path_template.format(corner=config.corner)
    netlist_file = config.netlist_path_template.format(benchmark=config.benchmark)
    sdc_file = config.sdc_path_template.format(benchmark=config.benchmark)
    
    # 创建输出目录
    output_dir = config.output_root / config.benchmark / "corners" / config.corner
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查文件存在
    if not Path(lib_file).exists():
        raise FileNotFoundError(f"Library file not found: {lib_file}")
    if not Path(netlist_file).exists():
        raise FileNotFoundError(f"Netlist file not found: {netlist_file}")
    
    has_sdc = Path(sdc_file).exists()
    if not has_sdc:
        print(f"  [WARNING] SDC file not found: {sdc_file} (will skip)")
    
    # 转换为WSL路径（如果OpenTimer在WSL中运行）
    def to_wsl_path(path: str) -> str:
        return path.replace('\\', '/').replace('D:', '/mnt/d')
    
    lib_path_wsl = to_wsl_path(lib_file)
    netlist_path_wsl = to_wsl_path(netlist_file)
    sdc_path_wsl = to_wsl_path(sdc_file) if has_sdc else ""
    output_dir_wsl = to_wsl_path(str(output_dir))
    
    # 生成TCL脚本（路径直接使用，OpenTimer不需要引号或花括号）
    tcl_content = f"""# Read library
read_celllib {lib_path_wsl}

# Read netlist
read_verilog {netlist_path_wsl}

# Read SDC constraints
"""
    if has_sdc:
        tcl_content += f'read_sdc {sdc_path_wsl}\n'
    
    tcl_content += f"""
# Update timing (must be done before any dump commands that require timing)
update_timing

# Check timing status
report_wns
report_tns

# Export static info first (doesn't require timing update)
dump_pin_static -o {output_dir_wsl}/pin_static.txt

# Export structural graph (doesn't require timing update, but may need after read_verilog)
# This provides the authoritative graph structure
dump_graph -o {output_dir_wsl}/graph.dot

# Export node dynamic features (requires timing update)
dump_at -o {output_dir_wsl}/arrival.txt
dump_slew -o {output_dir_wsl}/slew.txt
dump_pin_cap -o {output_dir_wsl}/pin_cap.txt

# Export edge/net features (requires timing update)
# Note: dump_arc_delay is the most important - do it first
dump_arc_delay -o {output_dir_wsl}/arc_delay.txt

# dump_net_load may cause issues if RC timing not fully updated, so we skip it or do it last
# dump_net_load -o {output_dir_wsl}/net_load.txt

# Export slack and RAT (if available)
dump_slack -o {output_dir_wsl}/slack.txt
dump_rat -o {output_dir_wsl}/rat.txt
"""
    
    # 写入临时TCL文件
    tcl_file = output_dir / "export.tcl"
    with open(tcl_file, 'w', encoding='utf-8') as f:
        f.write(tcl_content)
    
    # 运行OpenTimer（通过WSL）
    print(f"  Running OpenTimer for {config.benchmark}/{config.corner}...")
    print(f"  Library: {lib_file}")
    print(f"  Netlist: {netlist_file}")
    if has_sdc:
        print(f"  SDC: {sdc_file}")
    
    tcl_file_wsl = to_wsl_path(str(tcl_file))
    opentimer_bin = to_wsl_path(str(config.opentimer_path / "bin" / "ot-shell"))
    
    try:
        # 运行OpenTimer
        cmd = f"cd {to_wsl_path(str(config.opentimer_path))} && timeout 600 {opentimer_bin} < {tcl_file_wsl}"
        print(f"  Command: wsl bash -c \"{cmd[:100]}...\"")
        
        result = subprocess.run(
            ["wsl", "bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=600,
            encoding='utf-8',
            errors='replace'  # 处理编码错误
        )
        
        if result.returncode != 0:
            print(f"  [ERROR] OpenTimer failed with return code {result.returncode}")
            print(f"  Return code 134 usually means SIGABRT (program crashed)")
            
            if result.stderr:
                print(f"\n  stderr (first 1000 chars):")
                # 安全处理编码
                stderr_bytes = result.stderr[:1000].encode('utf-8', errors='replace')
                stderr_safe = stderr_bytes.decode('utf-8', errors='replace')
                # 写入文件而不是直接print，避免控制台编码问题
                error_log = output_dir / "opentimer_error.log"
                with open(error_log, 'w', encoding='utf-8', errors='replace') as f:
                    f.write("=== OpenTimer stderr ===\n")
                    f.write(result.stderr)
                    f.write("\n\n=== OpenTimer stdout ===\n")
                    f.write(result.stdout)
                print(f"  (Error details saved to: {error_log.name})")
                # 不打印，避免编码问题，直接告诉用户查看日志文件
                if len(result.stderr.strip()) > 0:
                    print(f"  stderr has {len(result.stderr)} characters")
                else:
                    print(f"  stderr is empty")
            if result.stdout:
                stdout_bytes = result.stdout[-1000:].encode('utf-8', errors='replace')
                stdout_safe = stdout_bytes.decode('utf-8', errors='replace')
                if len(result.stdout.strip()) > 0:
                    print(f"  stdout has {len(result.stdout)} characters (see log file for details)")
                else:
                    print(f"  stdout is empty")
            
            # 检查是否有部分文件生成
            partial_files = []
            for name, path in [('arrival', output_dir / "arrival.txt"),
                              ('slew', output_dir / "slew.txt"),
                              ('pin_static', output_dir / "pin_static.txt")]:
                if path.exists() and path.stat().st_size > 0:
                    partial_files.append(name)
            
            if partial_files:
                print(f"\n  [INFO] Some files were generated: {partial_files}")
                print(f"  [INFO] You can try --skip-opentimer mode with existing data")
            
            raise RuntimeError(f"OpenTimer export failed (return code {result.returncode})")
        
        # 检查导出的文件（arc_delay可能是.txt或.json）
        exported_files = {
            'arrival': output_dir / "arrival.txt",
            'slew': output_dir / "slew.txt",
            'pin_cap': output_dir / "pin_cap.txt",
            'pin_static': output_dir / "pin_static.txt",
            'net_load': output_dir / "net_load.txt",
            'graph': output_dir / "graph.dot"  # 结构dump
        }
        
        # arc_delay可能是.txt或.json
        arc_delay_txt = output_dir / "arc_delay.txt"
        arc_delay_json = output_dir / "arc_delay.json"
        if arc_delay_json.exists():
            exported_files['arc_delay'] = arc_delay_json
        elif arc_delay_txt.exists():
            exported_files['arc_delay'] = arc_delay_txt
        else:
            exported_files['arc_delay'] = None  # 标记为缺失
        
        # slack.txt和rat.txt（可选）
        slack_file = output_dir / "slack.txt"
        if slack_file.exists():
            exported_files['slack'] = slack_file
        
        rat_file = output_dir / "rat.txt"
        if rat_file.exists():
            exported_files['rat'] = rat_file
        
        # 等待文件系统同步（WSL文件系统可能需要时间）
        time.sleep(1)
        
        # 重新检查文件大小（可能文件还在写入）
        for name, path in list(exported_files.items()):
            if path and path.exists():
                # 等待文件大小稳定
                prev_size = -1
                for _ in range(5):
                    current_size = path.stat().st_size
                    if current_size == prev_size:
                        break
                    prev_size = current_size
                    time.sleep(0.2)
        
        # 检查必需的文件
        required_files = ['arrival', 'slew', 'pin_static', 'arc_delay']
        missing_files = [name for name in required_files 
                        if name not in exported_files or exported_files[name] is None 
                        or not exported_files[name].exists()]
        if missing_files:
            raise FileNotFoundError(f"Missing exported files: {missing_files}")
        
        # 检查可选文件
        if 'slack' not in exported_files:
            print(f"  [INFO] slack.txt not found (optional)")
        
        print(f"  [OK] All files exported successfully")
        for name, path in exported_files.items():
            if path and path.exists():
                size = path.stat().st_size
                print(f"    {name}: {size:,} bytes")
        
        return exported_files
        
    finally:
        # 清理临时TCL文件（除非指定保留）
        if not config.keep_tcl and tcl_file.exists():
            tcl_file.unlink()
        elif config.keep_tcl and tcl_file.exists():
            print(f"  [INFO] TCL file kept for debugging: {tcl_file.name}")


# ============================================================================
# Step2: 解析+清洗
# ============================================================================

def parse_graph_dot(dot_file: Path) -> List[Dict]:
    """
    解析OpenTimer的graph.dot文件，提取所有边（arcs）
    
    DOT格式示例：
    digraph G {
        "clk" -> "_387_:CLK" [label="net"];
        "_187_:A1" -> "_187_:Y" [label="cell"];
        ...
    }
    
    返回: List[Dict] with keys: src, dst, edge_type
    edge_type: 0=cell, 1=net
    """
    arcs = []
    
    if not dot_file.exists():
        return arcs
    
    with open(dot_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            # 跳过graph声明和结束
            if line.startswith('digraph') or line.startswith('graph') or line == '}':
                continue
            
            # 解析边：格式为 "src" -> "dst" [label="type"];
            # 或 "src" -> "dst" [label="net", color=...];
            # 或 "src" -> "dst" [label=net];
            if '->' in line:
                try:
                    # 移除末尾的分号
                    line = line.rstrip(';').strip()
                    
                    # 修复B：先提取label（支持多种格式），然后移除整个[...]段
                    edge_type = 0  # 默认cell
                    
                    # 提取label值（支持多种格式：label="net", label=net, label='net'）
                    label_match = re.search(r'label\s*=\s*["\']?([^"\'\]\s,]+)["\']?', line, re.IGNORECASE)
                    if label_match:
                        label = label_match.group(1).lower()
                        if label == 'net':
                            edge_type = 1
                        elif label == 'cell':
                            edge_type = 0
                    
                    # 修复B：移除整个[...]段（更通用，处理所有属性格式）
                    # 这样可以处理 [label="net", color=...], [label=net], [xlabel="..."] 等
                    line = re.sub(r'\[.*?\]', '', line).strip()
                    
                    # 提取src和dst
                    parts = line.split('->')
                    if len(parts) == 2:
                        # 修复：对src/dst做彻底清理，确保兼容不带引号的节点名
                        # 去除首尾空白、引号、可能的逗号等残留
                        src_str = parts[0].strip().strip('"').strip("'").rstrip(',').strip()
                        dst_str = parts[1].strip().strip('"').strip("'").rstrip(',').strip()
                        
                        src = normalize_pin_name(src_str)
                        dst = normalize_pin_name(dst_str)
                        
                        # 只添加有效的边
                        if is_valid_pin_name(src) and is_valid_pin_name(dst):
                            arcs.append({
                                'src': src,
                                'dst': dst,
                                'edge_type': edge_type
                            })
                except (ValueError, IndexError, AttributeError) as e:
                    # 解析失败，跳过这一行
                    continue
    
    return arcs


def is_standardized_arc_delay_json(arc_delay_file: Path) -> bool:
    """
    检测arc_delay.json是否已经是标准格式
    
    标准格式特征：
    1. 是JSON格式
    2. 包含'arcs'字段
    3. 所有arc都有'edge_id'字段
    4. edge_id连续（0, 1, 2, ..., n-1）
    5. 包含'edge_valid'字段（可选，但如果有则更确定）
    """
    if not arc_delay_file.exists() or arc_delay_file.suffix != '.json':
        return False
    
    try:
        with open(arc_delay_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict) or 'arcs' not in data:
                return False
            
            arcs = data['arcs']
            if not arcs:
                return False
            
            # 检查所有arc都有edge_id
            edge_ids = []
            for arc in arcs:
                if 'edge_id' not in arc:
                    return False
                eid = arc.get('edge_id')
                if not isinstance(eid, int):
                    return False
                edge_ids.append(eid)
            
            # 检查edge_id是否连续（0, 1, 2, ..., n-1）
            edge_ids_sorted = sorted(edge_ids)
            if edge_ids_sorted != list(range(len(arcs))):
                return False
            
            # 如果所有arc都有edge_valid字段，更确定是标准格式
            has_edge_valid = all('edge_valid' in arc for arc in arcs)
            
            return True
    except (json.JSONDecodeError, ValueError, KeyError):
        return False


def parse_arc_delay_txt(arc_delay_file: Path) -> List[Dict]:
    """
    解析arc_delay.txt文件
    
    支持多种格式：
    1. OpenTimer格式：
       From           To        Type         dRR         dRF         dFR         dFF   mRR   mRF   mFR   mFF
       clk    _387_:CLK         net    0.000000    0.000000    0.000000    0.000000     1     0     0     1
    2. 简单文本格式：src_pin dst_pin edge_type dRR dRF dFR dFF maskRR maskRF maskFR maskFF
    3. JSON格式：如果文件是JSON，直接解析
    """
    arcs = []
    
    # 尝试作为JSON解析
    try:
        with open(arc_delay_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'arcs' in data:
                # JSON格式，直接返回
                return data['arcs']
    except (json.JSONDecodeError, ValueError):
        pass
    
    # 作为文本格式解析
    with open(arc_delay_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # 查找header行
    header_line_idx = None
    for i, line in enumerate(lines):
        if 'From' in line and 'To' in line and 'Type' in line:
            header_line_idx = i
            break
    
    if header_line_idx is not None:
        # OpenTimer格式（有header）
        # 修复A4: 从header_line_idx+1开始，然后靠"跳分隔线"逻辑处理，避免漏首行数据
        start = header_line_idx + 1
        for line in lines[start:]:
            line = line.strip()
            if not line:
                continue
            # 跳过分隔线（可能包含多个-）
            if line.replace('-', '').strip() == '':
                continue
            # 跳过可能的重复header行
            if line.lower().startswith('from') and 'to' in line.lower():
                continue
            
            parts = line.split()
            # OpenTimer格式: From To Type dRR dRF dFR dFF mRR mRF mFR mFF (11个字段)
            if len(parts) < 11:
                continue
            
            try:
                # 格式: From To Type dRR dRF dFR dFF mRR mRF mFR mFF
                src = normalize_pin_name(parts[0])
                dst = normalize_pin_name(parts[1])
                type_str = parts[2].lower()
                edge_type = 1 if type_str == 'net' else 0  # net=1, cell=0
                dRR = float(parts[3])
                dRF = float(parts[4])
                dFR = float(parts[5])
                dFF = float(parts[6])
                maskRR = int(parts[7])
                maskRF = int(parts[8])
                maskFR = int(parts[9])
                maskFF = int(parts[10])
                
                arc = {
                    'src': src,
                    'dst': dst,
                    'edge_type': edge_type,
                    'delay': {
                        'dRR': dRR,
                        'dRF': dRF,
                        'dFR': dFR,
                        'dFF': dFF
                    },
                    'mask': {
                        'maskRR': maskRR,
                        'maskRF': maskRF,
                        'maskFR': maskFR,
                        'maskFF': maskFF
                    }
                }
                
                arcs.append(arc)
            except (ValueError, IndexError):
                continue
    else:
        # 简单文本格式（无header，直接是数据）
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            # 修复：与读取索引一致，需要11个字段（0-10）
            if len(parts) < 11:
                continue
            
            try:
                src = normalize_pin_name(parts[0])
                dst = normalize_pin_name(parts[1])
                edge_type = int(parts[2])
                dRR = float(parts[3])
                dRF = float(parts[4])
                dFR = float(parts[5])
                dFF = float(parts[6])
                maskRR = int(parts[7])
                maskRF = int(parts[8])
                maskFR = int(parts[9])
                maskFF = int(parts[10])
                
                arc = {
                    'src': src,
                    'dst': dst,
                    'edge_type': edge_type,
                    'delay': {
                        'dRR': dRR,
                        'dRF': dRF,
                        'dFR': dFR,
                        'dFF': dFF
                    },
                    'mask': {
                        'maskRR': maskRR,
                        'maskRF': maskRF,
                        'maskFR': maskFR,
                        'maskFF': maskFF
                    }
                }
                
                arcs.append(arc)
            except (ValueError, IndexError):
                continue
    
    return arcs


def parse_pin_static_txt(pin_static_file: Path) -> Dict[str, Dict]:
    """解析pin_static.txt文件"""
    pin_data = {}
    
    with open(pin_static_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # 查找header行
    header_line_idx = None
    for i, line in enumerate(lines):
        if 'Pin' in line and 'Fanin' in line and 'CellType' in line:
            header_line_idx = i
            break
    
    if header_line_idx is None:
        print(f"  [WARNING] Could not find header in pin_static.txt")
        return pin_data
    
    # 解析数据行
    # 修复A4: 从header_line_idx+1开始，然后靠"跳分隔线"逻辑处理，避免漏首行数据
    start = header_line_idx + 1
    for line in lines[start:]:
        line = line.strip()
        if not line:
            continue
        # 跳过分隔线
        if line.startswith('-') or line.replace('-', '').strip() == '':
            continue
        # 跳过可能的重复header行
        if line.lower().startswith('pin') and 'fanin' in line.lower():
            continue
        
        parts = line.split()
        if len(parts) >= 5:
            pin_name = normalize_pin_name(parts[0])
            try:
                fanin = int(parts[1])
                fanout = int(parts[2])
                cell_type = parts[3]
                pin_role = parts[4] if len(parts) > 4 else "N/A"
                
                pin_data[pin_name] = {
                    'fanin': fanin,
                    'fanout': fanout,
                    'cell_type': cell_type,
                    'pin_role': pin_role
                }
            except (ValueError, IndexError):
                continue
    
    return pin_data


def clean_and_deduplicate_arcs(
    raw_arcs: List[Dict],
    pin_static_data: Dict[str, Dict],
    config: Config,
    stats: ProcessingStats
) -> List[Dict]:
    """
    清洗和去重arcs
    
    1. 过滤无效pin name
    2. 过滤instance节点（如果配置要求）
    3. 按(src, dst, edge_type)分组去重
    4. 应用选优规则
    5. 修复Net arc的mask
    """
    print("\n" + "=" * 60)
    print("Step 2: Cleaning and Deduplicating Arcs")
    print("=" * 60)
    
    stats.num_raw_arcs = len(raw_arcs)
    print(f"\n[Step 2.1] Raw arcs: {stats.num_raw_arcs}")
    
    # 过滤无效pin name
    print(f"\n[Step 2.2] Filtering invalid pin names...")
    valid_arcs = []
    for arc in raw_arcs:
        src = arc.get('src', '')
        dst = arc.get('dst', '')
        if is_valid_pin_name(src) and is_valid_pin_name(dst):
            valid_arcs.append(arc)
        else:
            stats.num_invalid_pin_dropped += 1
    
    print(f"  Valid arcs: {len(valid_arcs)}")
    print(f"  Invalid arcs (dropped): {stats.num_invalid_pin_dropped}")
    
    # 过滤instance节点和PI/PO节点（如果配置要求）
    if not config.keep_instance or not config.keep_pi_po:
        print(f"\n[Step 2.3] Filtering nodes...")
        filtered_arcs = []
        for arc in valid_arcs:
            src = arc.get('src', '')
            dst = arc.get('dst', '')
            src_info = pin_static_data.get(src, {})
            dst_info = pin_static_data.get(dst, {})
            src_role = src_info.get('pin_role', '').upper()
            dst_role = dst_info.get('pin_role', '').upper()
            
            # 过滤instance节点
            if not config.keep_instance:
                if is_instance_node(src, src_info.get('pin_role')) or is_instance_node(dst, dst_info.get('pin_role')):
                    stats.num_instance_filtered += 1
                    continue
            
            # 修复C2: 过滤PI/PO节点（同步过滤边，避免node_static删了节点但graph_edges还有相关边）
            if not config.keep_pi_po:
                if src_role in ('PI', 'PO', 'IN', 'OUT', 'INPUT', 'OUTPUT') or \
                   dst_role in ('PI', 'PO', 'IN', 'OUT', 'INPUT', 'OUTPUT'):
                    continue
            
            filtered_arcs.append(arc)
        
        valid_arcs = filtered_arcs
        print(f"  Filtered arcs: {len(valid_arcs)}")
        if not config.keep_instance:
            print(f"  Instance arcs (dropped): {stats.num_instance_filtered}")
    
    # 按(src, dst, edge_type)分组
    print(f"\n[Step 2.4] Grouping arcs by (src, dst, edge_type)...")
    groups = defaultdict(list)
    for arc in valid_arcs:
        src = arc.get('src', '')
        dst = arc.get('dst', '')
        edge_type = arc.get('edge_type', 0)
        key = (src, dst, edge_type)
        groups[key].append(arc)
    
    stats.num_groups = len(groups)
    stats.num_conflict_groups = sum(1 for v in groups.values() if len(v) > 1)
    
    print(f"  Unique edge groups: {stats.num_groups}")
    print(f"  Groups with conflicts (>1 candidate): {stats.num_conflict_groups}")
    
    # 对每组应用选优规则
    print(f"\n[Step 2.5] Applying selection rules (A/B/C)...")
    selected_arcs = []
    
    # 修复A3: 按sorted keys遍历，确保稳定可复现（conflict_details顺序一致）
    for key in sorted(groups.keys(), key=lambda k: (k[2], k[0], k[1])):
        candidates = groups[key]
        src, dst, edge_type = key
        
        if len(candidates) == 1:
            selected = candidates[0]
            reason = 'single_candidate'
        else:
            selected, reason = select_best_arc(candidates)
            if len(stats.conflict_details) < 10:
                stats.conflict_details.append({
                    'src': src,
                    'dst': dst,
                    'edge_type': edge_type,
                    'num_candidates': len(candidates),
                    'selected_reason': reason
                })
        
        # 修复A：在fix_net_arc_mask之前检查原始mask，避免把"缺失边"变成"有效边但delay=0"
        # 先保存原始mask状态（用于判断是否为缺失边）
        original_mask = selected.get('mask', {}).copy()
        original_mask_sum = (original_mask.get('maskRR', 0) + 
                            original_mask.get('maskRF', 0) + 
                            original_mask.get('maskFR', 0) + 
                            original_mask.get('maskFF', 0))
        
        # 检查是否为全0（在fix之前检查，避免被net arc固定mask干扰）
        is_all_zero = is_all_zero_placeholder(selected) or (reason == 'all_zero_arc')
        
        # 修复：先检查被丢弃的占位符（在修改mask之前），避免cand != selected比较失效
        # 使用身份比较（is not）而不是内容比较（!=），确保正确统计
        if len(candidates) > 1:
            for cand in candidates:
                if cand is not selected and is_all_zero_placeholder(cand):
                    stats.num_placeholder_dropped += 1
        
        if is_all_zero:
            stats.num_all_zero_groups += 1
            if edge_type == 0:
                stats.cell_all_zero_count += 1
            else:
                stats.net_all_zero_count += 1
            
            # 关键：把占位符标记为缺失（mask全0），避免训练污染
            selected['mask'] = {'maskRR': 0, 'maskRF': 0, 'maskFR': 0, 'maskFF': 0}
        else:
            # 只有非占位符才修复net arc mask
            # 但要注意：如果原始mask全0（缺失边），不应该fix（避免把缺失边变成有效边）
            if edge_type == 1 and original_mask_sum > 0:
                # Net arc且原始mask不全0（有有效通道），才修复mask
                selected = fix_net_arc_mask(selected)
            elif edge_type == 1 and original_mask_sum == 0:
                # Net arc但原始mask全0（缺失边），保持mask全0，不修复
                # 这样在训练时可以通过edge_valid=0标记为无效边
                pass
            else:
                # Cell arc，不需要修复mask
                pass
        
        selected_arcs.append((key, selected))
    
    print(f"  Selected arcs: {len(selected_arcs)}")
    print(f"  All-zero groups: {stats.num_all_zero_groups}")
    print(f"  Placeholder arcs dropped: {stats.num_placeholder_dropped}")
    
    # 统计cell/net arcs
    stats.total_cell_arcs = sum(1 for _, arc in selected_arcs if arc.get('edge_type', 0) == 0)
    stats.total_net_arcs = sum(1 for _, arc in selected_arcs if arc.get('edge_type', 0) == 1)
    
    return [arc for _, arc in selected_arcs]


# ============================================================================
# Step3: 标准化输出+校验
# ============================================================================

def generate_graph_edges_from_structure(
    structure_arcs: List[Dict],
    output_file: Path,
    pin_static_data: Dict[str, Dict],
    config: Config
) -> Dict[Tuple[str, str, int], int]:
    """
    从结构dump生成graph_edges.csv（权威边定义）
    
    修复：从结构dump（DOT）生成，而不是从某个corner的arc_delay生成
    这样可以确保graph_edges.csv包含完整的图结构
    
    返回: key -> edge_id 映射
    """
    print("\n" + "=" * 60)
    print("Step 3.1: Generating graph_edges.csv from structural dump")
    print("=" * 60)
    
    # 应用过滤规则（与arc_delay处理一致）
    filtered_arcs = []
    for arc in structure_arcs:
        src = arc.get('src', '')
        dst = arc.get('dst', '')
        
        # 过滤无效pin name
        if not is_valid_pin_name(src) or not is_valid_pin_name(dst):
            continue
        
        # 过滤instance节点（如果配置要求）
        if not config.keep_instance:
            src_info = pin_static_data.get(src, {})
            dst_info = pin_static_data.get(dst, {})
            if is_instance_node(src, src_info.get('pin_role')) or is_instance_node(dst, dst_info.get('pin_role')):
                continue
        
        # 过滤PI/PO节点（如果配置要求）
        if not config.keep_pi_po:
            src_info = pin_static_data.get(src, {})
            dst_info = pin_static_data.get(dst, {})
            src_role = src_info.get('pin_role', '').upper()
            dst_role = dst_info.get('pin_role', '').upper()
            if src_role in ('PI', 'PO', 'IN', 'OUT', 'INPUT', 'OUTPUT') or \
               dst_role in ('PI', 'PO', 'IN', 'OUT', 'INPUT', 'OUTPUT'):
                continue
        
        filtered_arcs.append(arc)
    
    # 收集所有唯一的keys，按(edge_type, src, dst)排序确保确定性
    unique_keys = set()
    for arc in filtered_arcs:
        src = arc.get('src', '')
        dst = arc.get('dst', '')
        edge_type = arc.get('edge_type', 0)
        key = (src, dst, edge_type)
        unique_keys.add(key)
    
    # 按(edge_type, src, dst)排序，确保edge_id分配稳定
    sorted_keys = sorted(unique_keys, key=lambda k: (k[2], k[0], k[1]))
    
    edges = []
    key_to_edge_id = {}
    
    for edge_id, (src, dst, edge_type) in enumerate(sorted_keys):
        edges.append({
            'edge_id': edge_id,
            'src': src,
            'dst': dst,
            'edge_type': edge_type
        })
        key_to_edge_id[(src, dst, edge_type)] = edge_id
    
    # 写入CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['edge_id', 'src', 'dst', 'edge_type'])
        writer.writeheader()
        writer.writerows(edges)
    
    print(f"  Wrote {len(edges)} edges to {output_file.name} (from structural dump)")
    print(f"  Edge_id range: 0 - {len(edges)-1} (continuous)")
    
    return key_to_edge_id


def generate_graph_edges_csv(
    cleaned_arcs: List[Dict],
    output_file: Path
) -> Dict[Tuple[str, str, int], int]:
    """
    生成graph_edges.csv（权威边定义）- 从arc_delay生成（回退方案）
    
    修复A2: 按sorted unique keys分配edge_id，确保确定性（hash稳定、可复现）
    
    返回: key -> edge_id 映射
    """
    print("\n" + "=" * 60)
    print("Step 3.1: Generating graph_edges.csv (from arc_delay, fallback)")
    print("=" * 60)
    
    # 收集所有唯一的keys，按(edge_type, src, dst)排序确保确定性
    unique_keys = set()
    for arc in cleaned_arcs:
        src = arc.get('src', '')
        dst = arc.get('dst', '')
        edge_type = arc.get('edge_type', 0)
        key = (src, dst, edge_type)
        unique_keys.add(key)
    
    # 按(edge_type, src, dst)排序，确保edge_id分配稳定
    sorted_keys = sorted(unique_keys, key=lambda k: (k[2], k[0], k[1]))
    
    edges = []
    key_to_edge_id = {}
    
    for edge_id, (src, dst, edge_type) in enumerate(sorted_keys):
        edges.append({
            'edge_id': edge_id,
            'src': src,
            'dst': dst,
            'edge_type': edge_type
        })
        key_to_edge_id[(src, dst, edge_type)] = edge_id
    
    # 写入CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['edge_id', 'src', 'dst', 'edge_type'])
        writer.writeheader()
        writer.writerows(edges)
    
    print(f"  Wrote {len(edges)} edges to {output_file.name}")
    print(f"  Edge_id range: 0 - {len(edges)-1} (continuous)")
    
    return key_to_edge_id


def collect_pins_from_graph_edges(graph_edges_file: Path) -> Set[str]:
    """
    从graph_edges.csv收集所有src/dst pins的并集
    
    这是权威节点集合，与"graph_edges.csv是权威结构定义"完全一致
    """
    pins = set()
    with open(graph_edges_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pins.add(normalize_pin_name(row['src']))
            pins.add(normalize_pin_name(row['dst']))
    return pins


def generate_node_static_csv_from_structure(
    graph_edges_file: Path,
    pin_static_data: Dict[str, Dict],
    output_file: Path,
    config: Config
) -> Set[str]:
    """
    从graph_edges.csv生成node_static.csv（权威节点集合）
    
    关键修复：node_static不应该从arrival生成，而应该从"结构图"生成
    - 来自graph_edges.csv的所有src/dst pins的并集
    - 这与"graph_edges.csv是权威结构定义（B）"完全一致
    - 不再依赖任何corner的arrival覆盖情况
    
    返回: pin集合
    """
    print("\n" + "=" * 60)
    print("Step 3.2: Generating node_static.csv from graph_edges.csv")
    print("=" * 60)
    
    # 从graph_edges.csv获取权威pin集合
    all_pins = collect_pins_from_graph_edges(graph_edges_file)
    print(f"  Pins from graph_edges: {len(all_pins)}")
    
    # 过滤instance节点（如果配置要求）
    if not config.keep_instance:
        filtered_pins = set()
        for pin in all_pins:
            pin_info = pin_static_data.get(pin, {})
            pin_role = pin_info.get('pin_role')
            if not is_instance_node(pin, pin_role):
                filtered_pins.add(pin)
        all_pins = filtered_pins
        print(f"  After filtering instance nodes: {len(all_pins)} pins")
    
    # 过滤PI/PO节点（如果配置要求）
    if not config.keep_pi_po:
        def is_pipo(p):
            role = pin_static_data.get(p, {}).get('pin_role', '')
            return str(role).upper() in ('PI', 'PO', 'IN', 'OUT', 'INPUT', 'OUTPUT')
        filtered_pins = {p for p in all_pins if not is_pipo(p)}
        all_pins = filtered_pins
        print(f"  After filtering PI/PO nodes: {len(all_pins)} pins")
    
    sorted_pins = sorted(all_pins)
    
    # 生成CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['node_id', 'pin_name', 'fanin', 'fanout', 'cell_type', 'pin_role'])
        
        for node_id, pin in enumerate(sorted_pins):
            info = pin_static_data.get(pin)
            if info:
                writer.writerow([
                    node_id,
                    pin,
                    info['fanin'],
                    info['fanout'],
                    info['cell_type'],
                    info['pin_role']
                ])
            else:
                writer.writerow([node_id, pin, 0, 0, "N/A", "N/A"])
    
    print(f"  Generated {len(sorted_pins)} rows in {output_file.name}")
    
    # 生成node_id_map.json（pin_name → node_id 映射，便于训练时快速查找）
    node_id_map_file = output_file.parent / "node_id_map.json"
    node_id_map = {pin: node_id for node_id, pin in enumerate(sorted_pins)}
    with open(node_id_map_file, 'w', encoding='utf-8') as f:
        json.dump(node_id_map, f, indent=2, ensure_ascii=False)
    print(f"  Generated node_id_map.json: {len(node_id_map)} pin_name → node_id mappings")
    
    return set(sorted_pins)


# 保留旧函数作为向后兼容（已废弃，但保留以防万一）
def generate_node_static_csv(
    pin_static_data: Dict[str, Dict],
    arrival_file: Path,
    output_file: Path,
    config: Config
) -> Set[str]:
    """
    生成node_static.csv（已废弃：从arrival生成，不推荐）
    
    已废弃：应该使用generate_node_static_csv_from_structure()从graph_edges.csv生成
    """
    print("\n" + "=" * 60)
    print("Step 3.2: Generating node_static.csv (DEPRECATED: from arrival)")
    print("=" * 60)
    print("  [WARNING] This method is deprecated. Use generate_node_static_csv_from_structure() instead.")
    
    # 从arrival.txt获取权威pin集合
    arrival_pins = set()
    with open(arrival_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('Arrival') or line.startswith('-') or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 5:
                pin_name = normalize_pin_name(parts[-1])
                if pin_name.lower() not in ['pin', 'e/r', 'e/f', 'l/r', 'l/f']:
                    arrival_pins.add(pin_name)
    
    print(f"  Found {len(arrival_pins)} pins in arrival.txt")
    
    # 过滤instance节点（如果配置要求）
    if not config.keep_instance:
        filtered_pins = set()
        for pin in arrival_pins:
            pin_info = pin_static_data.get(pin, {})
            pin_role = pin_info.get('pin_role')
            if not is_instance_node(pin, pin_role):
                filtered_pins.add(pin)
        arrival_pins = filtered_pins
        print(f"  After filtering instance nodes: {len(arrival_pins)} pins")
    
    all_pins = arrival_pins
    
    # 过滤PI/PO节点
    if not config.keep_pi_po:
        filtered_pins = set()
        for pin in all_pins:
            pin_info = pin_static_data.get(pin, {})
            pin_role = pin_info.get('pin_role', '').upper()
            if pin_role not in ('PI', 'PO', 'IN', 'OUT', 'INPUT', 'OUTPUT'):
                filtered_pins.add(pin)
        all_pins = filtered_pins
        print(f"  After filtering PI/PO nodes: {len(all_pins)} pins")
    
    sorted_pins = sorted(all_pins)
    
    # 生成CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['node_id', 'pin_name', 'fanin', 'fanout', 'cell_type', 'pin_role'])
        
        for node_id, pin_name in enumerate(sorted_pins):
            if pin_name in pin_static_data:
                data = pin_static_data[pin_name]
                writer.writerow([
                    node_id,
                    pin_name,
                    data['fanin'],
                    data['fanout'],
                    data['cell_type'],
                    data['pin_role']
                ])
            else:
                writer.writerow([node_id, pin_name, 0, 0, "N/A", "N/A"])
    
    print(f"  Generated {len(sorted_pins)} rows in {output_file.name}")
    
    return set(sorted_pins)


def make_placeholder_arc(src: str, dst: str, edge_type: int, edge_id: int) -> Dict:
    """创建placeholder arc（缺失边，mask全0表示缺失）"""
    return {
        "src": src,
        "dst": dst,
        "edge_type": edge_type,
        "edge_id": edge_id,
        "delay": {"dRR": 0.0, "dRF": 0.0, "dFR": 0.0, "dFF": 0.0},
        "mask": {"maskRR": 0, "maskRF": 0, "maskFR": 0, "maskFF": 0},
        "edge_valid": 0  # 缺失边，无效
    }


def generate_arc_delay_json(
    cleaned_arcs: List[Dict],
    key_to_edge_id: Dict[Tuple[str, str, int], int],
    output_file: Path,
    config: Config
):
    """
    生成arc_delay.json（按edge_id对齐，按graph_edges.csv全集补齐）
    
    修复：按graph_edges.csv全集edge_id输出，缺失边用placeholder补齐（mask=0表缺失）
    这样可以保证edge coverage 100%
    """
    print("\n" + "=" * 60)
    print("Step 3.3: Generating arc_delay.json")
    print("=" * 60)
    
    # 强校验：检查cleaned_arcs中是否有graph_edges.csv中没有的边
    # 如果graph_edges.csv从第一个corner生成时缺边，后续corner的新边会被静默丢弃
    cleaned_arcs_keys = set()
    for arc in cleaned_arcs:
        src = arc.get('src', '')
        dst = arc.get('dst', '')
        edge_type = arc.get('edge_type', 0)
        key = (src, dst, edge_type)
        cleaned_arcs_keys.add(key)
    
    extra_keys = cleaned_arcs_keys - set(key_to_edge_id.keys())
    if extra_keys:
        # 输出样本以便调试
        sample_keys = list(extra_keys)[:10]
        sample_str = "\n    ".join([f"({k[0]} -> {k[1]}, type={k[2]})" for k in sample_keys])
        error_msg = (
            f"Found {len(extra_keys)} edges in cleaned_arcs that are NOT in graph_edges.csv.\n"
            f"graph_edges.csv may be incomplete (generated from a corner with missing edges).\n"
            f"Sample missing edges (first 10):\n    {sample_str}"
        )
        if len(extra_keys) > 10:
            error_msg += f"\n    ... and {len(extra_keys) - 10} more edges"
        error_msg += (
            f"\n\nThis indicates that graph_edges.csv was generated from a corner that "
            f"did not export all structural edges. Regenerate graph_edges.csv from a "
            f"complete structural dump or union all corners' edges."
        )
        raise RuntimeError(error_msg)
    
    # key -> arc（当前corner有的数据）
    key_to_arc = {}
    for arc in cleaned_arcs:
        src = arc.get('src', '')
        dst = arc.get('dst', '')
        edge_type = arc.get('edge_type', 0)
        key = (src, dst, edge_type)
        key_to_arc[key] = arc
    
    # 获取最大edge_id（确定数组大小）
    max_edge_id = max(key_to_edge_id.values()) if key_to_edge_id else -1
    
    # 修复B1: 一次性做反向映射edge_id_to_key，从O(E²)改为O(E)
    edge_id_to_key = [None] * (max_edge_id + 1)
    for key, eid in key_to_edge_id.items():
        if 0 <= eid <= max_edge_id:
            edge_id_to_key[eid] = key
    
    # 按edge_id连续输出（全集）
    arcs_json = []
    placeholder_count = 0
    
    for edge_id in range(max_edge_id + 1):
        key_for_edge_id = edge_id_to_key[edge_id]
        
        if key_for_edge_id is None:
            # 理论不应发生，但兜底处理
            placeholder_arc = make_placeholder_arc('', '', 0, edge_id)
            # placeholder的edge_valid=0（缺失边）
            placeholder_arc['edge_valid'] = 0
            arcs_json.append(placeholder_arc)
            placeholder_count += 1
            continue
        
        if key_for_edge_id in key_to_arc:
            # 有数据：使用实际arc
            arc_copy = key_to_arc[key_for_edge_id].copy()
            arc_copy['edge_id'] = edge_id
            
            # 修复A：添加edge_valid字段（用于训练时标记边的有效性）
            # edge_valid = 1 if mask_sum > 0 else 0
            # mask全0表示缺失/无效边，训练时应该忽略这些边的edge_attr和edge-level loss
            mask = arc_copy.get('mask', {})
            mask_sum = (mask.get('maskRR', 0) + 
                       mask.get('maskRF', 0) + 
                       mask.get('maskFR', 0) + 
                       mask.get('maskFF', 0))
            arc_copy['edge_valid'] = 1 if mask_sum > 0 else 0
            
            arcs_json.append(arc_copy)
        else:
            # 缺失：创建placeholder
            if key_for_edge_id:
                src, dst, edge_type = key_for_edge_id
            else:
                # 如果找不到key，使用默认值（理论上不应该发生）
                src, dst, edge_type = '', '', 0
            placeholder_arc = make_placeholder_arc(src, dst, edge_type, edge_id)
            # placeholder的edge_valid=0（缺失边）
            placeholder_arc['edge_valid'] = 0
            arcs_json.append(placeholder_arc)
            placeholder_count += 1
    
    # 写入JSON
    output_data = {
        'corner': config.corner,
        'time_unit': config.time_unit,
        'channel_order': ['RR', 'RF', 'FR', 'FF'],  # 通道语义: RR=rise→rise, RF=rise→fall, FR=fall→rise, FF=fall→fall
        'arcs': arcs_json
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"  Wrote {len(arcs_json)} arcs to {output_file.name}")
    print(f"  Placeholder arcs (missing): {placeholder_count}")
    print(f"  Actual arcs: {len(arcs_json) - placeholder_count}")


def parse_arrival_txt(arrival_file: Path) -> Dict[str, Dict]:
    """解析arrival.txt文件"""
    arrival_data = {}
    
    with open(arrival_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('Arrival') or line.startswith('-') or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 5:
                try:
                    # 修复D3: 用parts[-1]取pin，更鲁棒（兼容列数变化）
                    pin_name = normalize_pin_name(parts[-1])
                    # 过滤非法pin名（如 "_375_:" 这种没有pin的instance body）
                    if not is_valid_pin_name(pin_name):
                        continue
                    er, ef, lr, lf = map(float, parts[0:4])
                    
                    arrival_data[pin_name] = {
                        'ER': er,
                        'EF': ef,
                        'LR': lr,
                        'LF': lf
                    }
                except (ValueError, IndexError):
                    continue
    
    return arrival_data


def parse_slew_txt(slew_file: Path) -> Dict[str, Dict]:
    """解析slew.txt文件"""
    slew_data = {}
    
    with open(slew_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('Slew') or line.startswith('-') or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 5:
                try:
                    # 修复D3: 用parts[-1]取pin，更鲁棒（兼容列数变化）
                    pin_name = normalize_pin_name(parts[-1])
                    # 过滤非法pin名（如 "_375_:" 这种没有pin的instance body）
                    if not is_valid_pin_name(pin_name):
                        continue
                    er, ef, lr, lf = map(float, parts[0:4])
                    
                    slew_data[pin_name] = {
                        'ER': er,
                        'EF': ef,
                        'LR': lr,
                        'LF': lf
                    }
                except (ValueError, IndexError):
                    continue
    
    return slew_data


def parse_slack_txt(slack_file: Path) -> Dict[str, Dict]:
    """解析slack.txt文件"""
    slack_data = {}
    
    with open(slack_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('Slack') or line.startswith('-') or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 5:
                try:
                    # 修复D3: 用parts[-1]取pin，更鲁棒（兼容列数变化）
                    pin_name = normalize_pin_name(parts[-1])
                    er, ef, lr, lf = map(float, parts[0:4])
                    
                    slack_data[pin_name] = {
                        'ER': er,
                        'EF': ef,
                        'LR': lr,
                        'LF': lf
                    }
                except (ValueError, IndexError):
                    continue
    
    return slack_data


def parse_rat_txt(rat_file: Path) -> Dict[str, Dict]:
    """解析rat.txt文件（Required Arrival Time）"""
    rat_data = {}
    
    with open(rat_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('RAT') or line.startswith('Required') or line.startswith('-') or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 5:
                try:
                    # 修复D3: 用parts[-1]取pin，更鲁棒（兼容列数变化）
                    pin_name = normalize_pin_name(parts[-1])
                    er, ef, lr, lf = map(float, parts[0:4])
                    
                    rat_data[pin_name] = {
                        'ER': er,
                        'EF': ef,
                        'LR': lr,
                        'LF': lf
                    }
                except (ValueError, IndexError):
                    continue
    
    return rat_data


def filter_pin_dict(pin_data: Dict[str, Dict], keep_pins: Set[str]) -> Dict[str, Dict]:
    """
    过滤pin字典，只保留在keep_pins中的pins
    
    用于确保arrival/slew/slack/rat数据与node_static.csv对齐
    """
    return {k: v for k, v in pin_data.items() if k in keep_pins}


def write_arrival_txt(arrival_data: Dict[str, Dict], output_file: Path):
    """写入标准化的arrival.txt"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Arrival time [pins:{}]\n".format(len(arrival_data)))
        f.write("-" * 60 + "\n")
        f.write("       E/R         E/F         L/R         L/F          Pin\n")
        f.write("-" * 60 + "\n")
        
        for pin_name in sorted(arrival_data.keys()):
            data = arrival_data[pin_name]
            f.write(f"  {data['ER']:10.6f}  {data['EF']:10.6f}  {data['LR']:10.6f}  {data['LF']:10.6f}  {pin_name}\n")


def write_slew_txt(slew_data: Dict[str, Dict], output_file: Path):
    """写入标准化的slew.txt"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Slew [pins:{}]\n".format(len(slew_data)))
        f.write("-" * 60 + "\n")
        f.write("       E/R         E/F         L/R         L/F          Pin\n")
        f.write("-" * 60 + "\n")
        
        for pin_name in sorted(slew_data.keys()):
            data = slew_data[pin_name]
            f.write(f"  {data['ER']:10.6f}  {data['EF']:10.6f}  {data['LR']:10.6f}  {data['LF']:10.6f}  {pin_name}\n")


def write_slack_txt(slack_data: Dict[str, Dict], output_file: Path):
    """写入标准化的slack.txt"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Slack [pins:{}]\n".format(len(slack_data)))
        f.write("-" * 60 + "\n")
        f.write("       E/R         E/F         L/R         L/F          Pin\n")
        f.write("-" * 60 + "\n")
        
        for pin_name in sorted(slack_data.keys()):
            data = slack_data[pin_name]
            f.write(f"  {data['ER']:10.6f}  {data['EF']:10.6f}  {data['LR']:10.6f}  {data['LF']:10.6f}  {pin_name}\n")


def write_rat_txt(rat_data: Dict[str, Dict], output_file: Path):
    """写入标准化的rat.txt（Required Arrival Time）"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("RAT [pins:{}]\n".format(len(rat_data)))
        f.write("-" * 60 + "\n")
        f.write("       E/R         E/F         L/R         L/F          Pin\n")
        f.write("-" * 60 + "\n")
        
        for pin_name in sorted(rat_data.keys()):
            data = rat_data[pin_name]
            f.write(f"  {data['ER']:10.6f}  {data['EF']:10.6f}  {data['LR']:10.6f}  {data['LF']:10.6f}  {pin_name}\n")


def parse_pin_cap_txt(pin_cap_file: Path) -> Dict[str, Dict]:
    """解析pin_cap.txt文件：E/R E/F L/R L/F Pin"""
    cap_data = {}
    with open(pin_cap_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            # 修复：跳过标题行、表头行和分隔线
            # 跳过标题行：Pin Capacitance [pins:1078]
            if line.startswith('Pin Capacitance'):
                continue
            # 跳过分隔线
            if line.startswith('-') or not line:
                continue
            # 跳过表头行：包含 E/R 且包含 Pin（如 "       E/R         E/F         L/R         L/F          Pin"）
            if 'E/R' in line and 'Pin' in line:
                continue
            
            parts = line.split()
            # 期望至少 5 列：ER EF LR LF Pin
            if len(parts) < 5:
                continue
            try:
                er, ef, lr, lf = map(float, parts[0:4])
                pin_name = normalize_pin_name(parts[-1])
                # 可选：丢弃明显非法 pin（如 "_375_:"）
                if not is_valid_pin_name(pin_name):
                    continue
                cap_data[pin_name] = {"ER": er, "EF": ef, "LR": lr, "LF": lf}
            except (ValueError, IndexError):
                continue
    return cap_data


def write_pin_cap_txt(cap_data: Dict[str, Dict], output_file: Path):
    """写入标准化的pin_cap.txt"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Pin Capacitance [pins:{}]\n".format(len(cap_data)))
        f.write("-" * 60 + "\n")
        f.write("       E/R         E/F         L/R         L/F          Pin\n")
        f.write("-" * 60 + "\n")
        for pin_name in sorted(cap_data.keys()):
            d = cap_data[pin_name]
            f.write(f"  {d['ER']:10.6f}  {d['EF']:10.6f}  {d['LR']:10.6f}  {d['LF']:10.6f}  {pin_name}\n")


def generate_endpoints_csv(
    arrival_data: Dict[str, Dict],
    slack_data: Dict[str, Dict],
    rat_data: Dict[str, Dict],
    pin_static_data: Dict[str, Dict],
    static_pins: Set[str],
    output_file: Path,
    config: Config
):
    """
    生成endpoints.csv文件
    
    修正策略（根据用户反馈）：
    1. 只导出有 slack 和 required 的 endpoints（避免空标签污染）
    2. 优先使用 slack_data 和 rat_data 的交集作为有效 endpoints
    3. 添加 coverage 统计和自洽性验证
    4. 确保 endpoint_pin 必须属于 node_static 的 pin 集合
    
    格式：
    endpoint_pin, rf, slack_late, arrival_late, required_late, valid
    
    其中：
    - endpoint_pin: endpoint pin名称（必须和 node_static.csv 的 pin_name 完全一致）
    - rf: 'R' (rise) 或 'F' (fall)
    - slack_late: late slack值（主监督标签）
    - arrival_late: late arrival time（用于传播一致性、排查异常）
    - required_late: required time（用于校验 slack = required - arrival）
    - valid: 1 表示有效（slack ≈ required - arrival），0 表示无效
    """
    print("\n" + "=" * 60)
    print("Step 3.6: Generating endpoints.csv")
    print("=" * 60)
    
    # 修正1：优先使用 slack_data 和 rat_data 的交集作为有效 endpoints
    # 这样可以自动过滤掉 unconstrained nodes
    slack_pins = set(slack_data.keys())
    rat_pins = set(rat_data.keys())
    arrival_pins = set(arrival_data.keys())
    
    # 有效 endpoints = 同时有 slack、rat 和 arrival 的 pins
    # 修复：直接用 valid_endpoints 作为最终 endpoints，不再用 pin_role 过滤
    # 因为"有 slack+rat 的 pin"本身就代表被约束/是 endpoint（或至少是你能监督的点）
    # pin_role 过滤会引入库差异造成的漏标（不同库可能用 Q/QN/O/ZN/Z/Y/OUT 等混用）
    valid_endpoints = slack_pins & rat_pins & arrival_pins
    
    print(f"  Slack pins: {len(slack_pins)}")
    print(f"  RAT pins: {len(rat_pins)}")
    print(f"  Arrival pins: {len(arrival_pins)}")
    print(f"  Valid endpoints (slack & rat & arrival): {len(valid_endpoints)}")
    
    # 修复：确保 endpoint_pin 必须属于 node_static 的 pin 集合
    # 虽然 arrival/slack/rat 已经按 static_pins 过滤过，但为了安全再次过滤
    final_endpoints = valid_endpoints & static_pins
    
    if len(valid_endpoints) != len(final_endpoints):
        dropped = valid_endpoints - static_pins
        print(f"  [WARNING] Dropped {len(dropped)} endpoints not in static_pins")
        if len(dropped) <= 10:
            print(f"    Dropped endpoints: {dropped}")
        else:
            print(f"    Dropped endpoints: {len(dropped)} (showing first 10)")
            sample_dropped = list(dropped)[:10]
            print(f"    Sample: {sample_dropped}")
    
    print(f"  Final endpoints: {len(final_endpoints)}")
    
    # 生成CSV - 只导出有完整数据的行
    rows = []
    valid_rows = 0
    
    for pin_name in sorted(final_endpoints):
        arrival_info = arrival_data.get(pin_name, {})
        slack_info = slack_data.get(pin_name, {})
        rat_info = rat_data.get(pin_name, {})
        
        # Rise通道
        lr_arrival = arrival_info.get('LR')
        lr_slack = slack_info.get('LR')
        lr_rat = rat_info.get('LR')
        
        # 只导出有完整数据的行
        if lr_arrival is not None and lr_slack is not None and lr_rat is not None:
            # 验证自洽性：slack ≈ required - arrival
            expected_slack = lr_rat - lr_arrival
            slack_diff = abs(lr_slack - expected_slack)
            is_valid = slack_diff < 0.0011  # 允许小的数值误差（浮点数精度问题，0.001 是常见的舍入误差）
            
            rows.append({
                'endpoint_pin': pin_name,
                'rf': 'R',
                'slack_late': lr_slack,
                'arrival_late': lr_arrival,
                'required_late': lr_rat,
                'valid': 1 if is_valid else 0
            })
            if is_valid:
                valid_rows += 1
        
        # Fall通道
        lf_arrival = arrival_info.get('LF')
        lf_slack = slack_info.get('LF')
        lf_rat = rat_info.get('LF')
        
        # 只导出有完整数据的行
        if lf_arrival is not None and lf_slack is not None and lf_rat is not None:
            # 验证自洽性：slack ≈ required - arrival
            expected_slack = lf_rat - lf_arrival
            slack_diff = abs(lf_slack - expected_slack)
            is_valid = slack_diff < 0.0011  # 允许小的数值误差（浮点数精度问题，0.001 是常见的舍入误差）
            
            rows.append({
                'endpoint_pin': pin_name,
                'rf': 'F',
                'slack_late': lf_slack,
                'arrival_late': lf_arrival,
                'required_late': lf_rat,
                'valid': 1 if is_valid else 0
            })
            if is_valid:
                valid_rows += 1
    
    # 写入CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['endpoint_pin', 'rf', 'slack_late', 'arrival_late', 'required_late', 'valid'])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"  Wrote {len(rows)} endpoint entries to {output_file.name}")
    print(f"  Valid entries (self-consistent): {valid_rows}/{len(rows)} ({valid_rows/len(rows)*100:.1f}%)" if len(rows) > 0 else "  No valid entries")
    
    # 统计信息
    if len(rows) == 0:
        print(f"  [WARNING] No valid endpoint entries generated - check slack.txt and rat.txt availability")
    else:
        print(f"  [OK] Generated {len(rows)} valid endpoint entries with complete slack/required/arrival data")
        print(f"  [INFO] Using all pins with slack+rat+arrival as endpoints (no pin_role filtering)")


def compute_file_hash(file_path: Path) -> str:
    """计算文件hash（用于校验）"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def validate_corner_data(
    corner_dir: Path,
    static_dir: Path,
    config: Config,
    stats: ProcessingStats
) -> Dict:
    """
    校验corner数据（必做校验）
    
    G. 必做校验：
    - pin coverage：corner pins必须==node_static pins（允许极小差异但要报警）
    - edge coverage：arc_delay必须覆盖全部edge_id
    - hash校验：同benchmark不同corner的graph_edges.csv hash必须一致
    - 数值sanity：delay/arrival/slew不应全为0或全为n/a
    """
    print("\n" + "=" * 60)
    print("Step 3.4: Validation")
    print("=" * 60)
    
    validation_results = {
        'pin_coverage_ok': False,
        'edge_coverage_ok': False,
        'hash_ok': True,  # 需要与其他corners比较
        'sanity_ok': False,
        'errors': []
    }
    
    # 1. Pin coverage检查
    print("\n[Validation 1] Pin coverage check...")
    node_static_file = static_dir / "node_static.csv"
    if not node_static_file.exists():
        validation_results['errors'].append("node_static.csv not found")
        return validation_results
    
    # 读取node_static pins
    static_pins = set()
    with open(node_static_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            static_pins.add(normalize_pin_name(row['pin_name']))
    
    print(f"  Static pins: {len(static_pins)}")
    
    # 修复：扩展检查所有pin数据文件，不仅检查arrival
    # 检查：arrival, slew, pin_cap, slack, rat 的 pins 是否都 ⊆ static_pins
    # 这样可以发现系统性的命名问题（比如 normalize 不一致）
    
    def check_pin_coverage(pin_data: Dict[str, Dict], data_name: str, static_pins: Set[str]) -> bool:
        """检查pin数据是否完全包含在static_pins中"""
        if not pin_data:
            return True  # 空数据，跳过检查
        
        data_pins = set(pin_data.keys())
        intersection = data_pins & static_pins
        coverage = len(intersection) / len(data_pins) if len(data_pins) > 0 else 0.0
        
        print(f"  {data_name} pins: {len(data_pins)}")
        print(f"  Coverage ({data_name} subset of static): {coverage:.4f} ({len(intersection)}/{len(data_pins)})")
        
        if coverage >= PIN_COVERAGE_THRESHOLD:
            print(f"  [OK] {data_name} coverage >= {PIN_COVERAGE_THRESHOLD*100:.1f}% ({data_name} subset of static)")
            return True
        else:
            missing_in_static = data_pins - static_pins
            validation_results['errors'].append(
                f"{data_name} pins not covered by node_static: {len(missing_in_static)} "
                f"(coverage: {coverage*100:.2f}% < {PIN_COVERAGE_THRESHOLD*100:.1f}%)"
            )
            print(f"  [WARNING] {data_name} coverage {coverage*100:.2f}% < {PIN_COVERAGE_THRESHOLD*100:.1f}%")
            if len(missing_in_static) <= 10:
                print(f"    Missing in static: {missing_in_static}")
            else:
                print(f"    Missing in static: {len(missing_in_static)} pins (showing first 10)")
                sample_missing = list(missing_in_static)[:10]
                print(f"    Sample: {sample_missing}")
            return False
    
    # 检查所有pin数据文件
    all_coverages_ok = True
    
    # 检查arrival.txt（必需）
    arrival_file = corner_dir / "arrival.txt"
    if arrival_file.exists():
        arrival_data = parse_arrival_txt(arrival_file)
        if not check_pin_coverage(arrival_data, "Arrival", static_pins):
            all_coverages_ok = False
    else:
        validation_results['errors'].append("arrival.txt not found")
        all_coverages_ok = False
    
    # 检查slew.txt（必需）
    slew_file = corner_dir / "slew.txt"
    if slew_file.exists():
        slew_data = parse_slew_txt(slew_file)
        if not check_pin_coverage(slew_data, "Slew", static_pins):
            all_coverages_ok = False
    
    # 检查pin_cap.txt（可选）
    pin_cap_file = corner_dir / "pin_cap.txt"
    if pin_cap_file.exists():
        pin_cap_data = parse_pin_cap_txt(pin_cap_file)
        if not check_pin_coverage(pin_cap_data, "PinCap", static_pins):
            all_coverages_ok = False
    
    # 检查slack.txt（可选）
    slack_file = corner_dir / "slack.txt"
    if slack_file.exists():
        slack_data = parse_slack_txt(slack_file)
        if not check_pin_coverage(slack_data, "Slack", static_pins):
            all_coverages_ok = False
    
    # 检查rat.txt（可选）
    rat_file = corner_dir / "rat.txt"
    if rat_file.exists():
        rat_data = parse_rat_txt(rat_file)
        if not check_pin_coverage(rat_data, "RAT", static_pins):
            all_coverages_ok = False
    
    if all_coverages_ok:
        validation_results['pin_coverage_ok'] = True
    
    # 2. Edge coverage检查
    print("\n[Validation 2] Edge coverage check...")
    graph_edges_file = static_dir / "graph_edges.csv"
    arc_delay_file = corner_dir / "arc_delay.json"
    
    if graph_edges_file.exists() and arc_delay_file.exists():
        # 读取graph_edges edge_ids
        edge_ids_static = set()
        with open(graph_edges_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                edge_ids_static.add(int(row['edge_id']))
        
        # 读取arc_delay edge_ids
        with open(arc_delay_file, 'r', encoding='utf-8') as f:
            arc_delay_data = json.load(f)
        edge_ids_arc = set()
        # 修复D2: 过滤None，避免意外缺edge_id的情况
        for arc in arc_delay_data.get('arcs', []):
            eid = arc.get('edge_id')
            if isinstance(eid, int):
                edge_ids_arc.add(eid)
        
        intersection = edge_ids_arc & edge_ids_static
        coverage_ratio = len(intersection) / len(edge_ids_static) if len(edge_ids_static) > 0 else 0.0
        
        print(f"  Static edges: {len(edge_ids_static)}")
        print(f"  Arc delay edges: {len(edge_ids_arc)}")
        print(f"  Intersection: {len(intersection)}")
        print(f"  Coverage ratio: {coverage_ratio:.4f}")
        
        if coverage_ratio >= EDGE_COVERAGE_THRESHOLD:
            validation_results['edge_coverage_ok'] = True
            print(f"  [OK] Edge coverage >= {EDGE_COVERAGE_THRESHOLD*100:.1f}%")
        else:
            missing = edge_ids_static - edge_ids_arc
            validation_results['errors'].append(
                f"Edge coverage {coverage_ratio*100:.2f}% < {EDGE_COVERAGE_THRESHOLD*100:.1f}% "
                f"(missing {len(missing)} edge_ids)"
            )
            print(f"  [WARNING] Edge coverage {coverage_ratio*100:.2f}% < {EDGE_COVERAGE_THRESHOLD*100:.1f}%")
    
    # 3. Hash校验（需要与其他corners比较，这里只记录）
    print("\n[Validation 3] Hash check (will compare with other corners)...")
    if graph_edges_file.exists():
        graph_edges_hash = compute_file_hash(graph_edges_file)
        print(f"  graph_edges.csv hash: {graph_edges_hash[:16]}...")
        validation_results['graph_edges_hash'] = graph_edges_hash
    
    # 4. 数值sanity检查
    print("\n[Validation 4] Value sanity check...")
    if arc_delay_file.exists():
        with open(arc_delay_file, 'r', encoding='utf-8') as f:
            arc_delay_data = json.load(f)
        
        arcs = arc_delay_data.get('arcs', [])
        if arcs:
            # 检查是否有非零值（只统计mask=1的有效通道，避免placeholder的0稀释统计）
            has_nonzero = False
            delay_values = []
            placeholder_count = 0
            for arc in arcs:
                mask = arc.get('mask', {})
                # 检查是否为placeholder（mask全0）
                if (mask.get('maskRR', 0) == 0 and mask.get('maskRF', 0) == 0 and 
                    mask.get('maskFR', 0) == 0 and mask.get('maskFF', 0) == 0):
                    placeholder_count += 1
                    continue
                
                delay = arc.get('delay', {})
                # 修复：统计所有mask=1的有效通道（RR/RF/FR/FF），避免误判
                # 因为cell arc很多时候RF/FR也会有值，如果只统计RR/FF可能误报"全0"
                if mask.get('maskRR', 0) == 1:
                    delay_values.append(delay.get('dRR', 0))
                if mask.get('maskRF', 0) == 1:
                    delay_values.append(delay.get('dRF', 0))
                if mask.get('maskFR', 0) == 1:
                    delay_values.append(delay.get('dFR', 0))
                if mask.get('maskFF', 0) == 1:
                    delay_values.append(delay.get('dFF', 0))
            
            if delay_values:
                min_delay = min(delay_values)
                max_delay = max(delay_values)
                mean_delay = sum(delay_values) / len(delay_values)
                
                print(f"  Delay stats (mask=1 only): min={min_delay:.6f}, max={max_delay:.6f}, mean={mean_delay:.6f}")
                print(f"  Placeholder arcs (mask=0): {placeholder_count}/{len(arcs)} ({placeholder_count/len(arcs)*100:.1f}%)")
                
                if max_delay > EPS:
                    validation_results['sanity_ok'] = True
                    print(f"  [OK] Has non-zero delay values")
                else:
                    validation_results['errors'].append("All delay values are zero")
                    print(f"  [WARNING] All delay values are zero")
    
    return validation_results


def generate_splits_json(
    output_root: Path,
    benchmark: str
) -> Path:
    """
    生成splits.json文件，定义anchors/train_targets/val_targets/test_targets的corner列表
    
    格式：
    {
        "anchors": ["ff1p16vn40c", "tt0p85v25c", "ss0p7v25c"],  # input only
        "train_targets": [...],  # supervision targets (exclude anchors)
        "val_targets": [...],
        "test_targets": [...],
        "all_corners": [...]
    }
    
    注意：anchors只做输入特征，不当监督target（避免trivial identity）
    """
    splits_file = output_root / benchmark / "splits.json"
    
    splits_data = {
        "anchors": ANCHORS,                 # input only
        "train_targets": TRAIN_TARGETS,     # supervision targets (exclude anchors)
        "val_targets": VAL_TARGETS,
        "test_targets": TEST_TARGETS,
        "all_corners": ALL_CORNERS
    }
    
    with open(splits_file, 'w', encoding='utf-8') as f:
        json.dump(splits_data, f, indent=2, ensure_ascii=False)
    
    print(
        f"  [OK] Generated splits.json: {len(ANCHORS)} anchors, "
        f"{len(TRAIN_TARGETS)} train_targets, {len(VAL_TARGETS)} val_targets, "
        f"{len(TEST_TARGETS)} test_targets"
    )
    
    return splits_file


def generate_meta_json(
    static_dir: Path,
    corner_dir: Path,
    config: Config,
    stats: ProcessingStats,
    validation_results: Dict
) -> Path:
    """
    生成meta.json（分离静态和corner特定数据）
    
    修复：避免27个corner反复覆盖static/meta.json导致数据污染
    
    生成两个文件：
    1. static/meta_static.json - 静态结构信息（num_edges, num_pins, hash, config）
       只在首次生成时写入，后续不覆盖
    2. corners/{corner}/meta_corner.json - corner特定信息（corner, stats, validation, opentimer_version）
       每个corner独立存储
    """
    print("\n" + "=" * 60)
    print("Step 3.5: Generating meta.json")
    print("=" * 60)
    
    # 读取graph_edges.csv统计
    graph_edges_file = static_dir / "graph_edges.csv"
    num_edges = 0
    if graph_edges_file.exists():
        with open(graph_edges_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            num_edges = sum(1 for _ in reader)
    
    # 读取node_static.csv统计
    node_static_file = static_dir / "node_static.csv"
    num_pins = 0
    if node_static_file.exists():
        with open(node_static_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            num_pins = sum(1 for _ in reader)
    
    # 计算统计信息
    cell_all_zero_ratio = stats.cell_all_zero_count / stats.total_cell_arcs if stats.total_cell_arcs > 0 else 0.0
    net_all_zero_ratio = stats.net_all_zero_count / stats.total_net_arcs if stats.total_net_arcs > 0 else 0.0
    conflict_groups_ratio = stats.num_conflict_groups / stats.num_groups if stats.num_groups > 0 else 0.0
    all_zero_ratio = stats.num_all_zero_groups / stats.num_groups if stats.num_groups > 0 else 0.0
    
    # 提取graph_edges_hash（如果存在）
    graph_edges_hash = validation_results.get('graph_edges_hash', '')
    
    # 1. 静态元数据（只在首次生成时写入，避免覆盖）
    meta_static = {
        'benchmark': config.benchmark,
        'num_edges': num_edges,
        'num_pins': num_pins,
        'graph_edges_hash': graph_edges_hash,
        'config': {
            'keep_pi_po': config.keep_pi_po,
            'keep_instance': config.keep_instance
        }
    }
    
    # 2. Corner特定元数据
    meta_corner = {
        'benchmark': config.benchmark,
        'corner': config.corner,
        'time_unit': config.time_unit,
        'opentimer_version': config.opentimer_version or 'unknown',
        'processing_stats': {
            'num_raw_arcs': stats.num_raw_arcs,
            'num_invalid_pin_dropped': stats.num_invalid_pin_dropped,
            'num_instance_filtered': stats.num_instance_filtered,
            'num_groups': stats.num_groups,
            'num_conflict_groups': stats.num_conflict_groups,
            'conflict_groups_ratio': conflict_groups_ratio,
            'num_all_zero_groups': stats.num_all_zero_groups,
            'all_zero_ratio': all_zero_ratio,
            'cell_all_zero_count': stats.cell_all_zero_count,
            'net_all_zero_count': stats.net_all_zero_count,
            'total_cell_arcs': stats.total_cell_arcs,
            'total_net_arcs': stats.total_net_arcs,
            'cell_all_zero_ratio': cell_all_zero_ratio,
            'net_all_zero_ratio': net_all_zero_ratio
        },
        'validation': validation_results
    }
    
    # 写入static/meta_static.json（只在不存在时写入，避免被覆盖）
    meta_static_file = static_dir / "meta_static.json"
    if not meta_static_file.exists():
        with open(meta_static_file, 'w', encoding='utf-8') as f:
            json.dump(meta_static, f, indent=2, ensure_ascii=False)
        print(f"  Wrote meta_static.json to {static_dir.name}")
    else:
        print(f"  [INFO] meta_static.json already exists, skipping (avoid overwrite)")
    
    # 写入corners/{corner}/meta_corner.json（每个corner独立存储）
    meta_corner_file = corner_dir / "meta_corner.json"
    with open(meta_corner_file, 'w', encoding='utf-8') as f:
        json.dump(meta_corner, f, indent=2, ensure_ascii=False)
    print(f"  Wrote meta_corner.json to corners/{config.corner}/")
    
    # 检查cell_all_zero_ratio报警
    if cell_all_zero_ratio > CELL_ALL_ZERO_THRESHOLD:
        print(f"  [WARNING] Cell all-zero ratio ({cell_all_zero_ratio*100:.2f}%) "
              f"exceeds threshold ({CELL_ALL_ZERO_THRESHOLD*100:.0f}%)")
    
    return meta_corner_file


# ============================================================================
# 主函数
# ============================================================================

def process_single_corner(config: Config) -> Dict:
    """
    处理单个corner的完整流程
    
    返回处理结果字典
    """
    print("\n" + "=" * 80)
    print(f"Processing: {config.benchmark} / {config.corner}")
    print("=" * 80)
    
    stats = ProcessingStats()
    
    try:
        # Step1: OpenTimer导出（或使用现有数据）
        if config.skip_opentimer and config.existing_data_dir:
            print("\n" + "=" * 60)
            print("Step 1: Using Existing Data (Skipping OpenTimer Export)")
            print("=" * 60)
            exported_files = {}
            # 查找现有数据文件
            data_dir = config.existing_data_dir
            if (data_dir / "arc_delay.json").exists():
                exported_files['arc_delay'] = data_dir / "arc_delay.json"
            elif (data_dir / "arc_delay.txt").exists():
                exported_files['arc_delay'] = data_dir / "arc_delay.txt"
            else:
                raise FileNotFoundError(f"arc_delay file not found in {data_dir}")
            
            exported_files['arrival'] = data_dir / "arrival.txt"
            exported_files['slew'] = data_dir / "slew.txt"
            
            # pin_static可能在当前目录或父目录
            if (data_dir / "pin_static.txt").exists():
                exported_files['pin_static'] = data_dir / "pin_static.txt"
            elif (data_dir.parent / "pin_static.txt").exists():
                exported_files['pin_static'] = data_dir.parent / "pin_static.txt"
            else:
                raise FileNotFoundError(f"pin_static.txt not found in {data_dir} or {data_dir.parent}")
            
            # slack和rat（可选）
            if (data_dir / "slack.txt").exists():
                exported_files['slack'] = data_dir / "slack.txt"
            if (data_dir / "rat.txt").exists():
                exported_files['rat'] = data_dir / "rat.txt"
            
            # graph.dot（结构，可选，但struct anchor需要）
            if (data_dir / "graph.dot").exists():
                exported_files["graph"] = data_dir / "graph.dot"
            elif (data_dir.parent / "graph.dot").exists():
                exported_files["graph"] = data_dir.parent / "graph.dot"
            
            # 检查必需文件存在
            # 注意：graph.dot 不在 required_files 中，因为只有 struct anchor 需要它
            required_files = ['arrival', 'slew', 'pin_static', 'arc_delay']
            missing = [name for name in required_files if name not in exported_files or not exported_files[name].exists()]
            if missing:
                raise FileNotFoundError(f"Missing files: {missing}")
            
            print(f"  Using existing data from: {data_dir}")
            for name, path in exported_files.items():
                if path.exists():
                    print(f"    {name}: {path.name} ({path.stat().st_size:,} bytes)")
        else:
            exported_files = run_opentimer_export(config)
        
        # Step3: 标准化输出+校验（先创建目录）
        # 创建输出目录
        static_dir = config.output_root / config.benchmark / "static"
        static_dir.mkdir(parents=True, exist_ok=True)
        
        corner_dir = config.output_root / config.benchmark / "corners" / config.corner
        corner_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查输入的arc_delay.json是否已经是标准格式（在skip-opentimer模式下）
        is_standardized = False
        if config.skip_opentimer and exported_files.get('arc_delay') and exported_files['arc_delay'].suffix == '.json':
            is_standardized = is_standardized_arc_delay_json(exported_files['arc_delay'])
            if is_standardized:
                print(f"\n  [INFO] Detected standardized arc_delay.json format - skipping Step2 (cleaning/deduplication)")
                print(f"  [INFO] Will directly use existing arc_delay.json and only perform validation")
        
        # Step2: 解析+清洗（如果不是标准格式）
        if not is_standardized:
            # 解析arc_delay（支持.txt和.json格式，parse_arc_delay_txt已支持两种格式）
            raw_arcs = parse_arc_delay_txt(exported_files['arc_delay'])
            
            # 解析pin_static.txt
            pin_static_data = parse_pin_static_txt(exported_files['pin_static'])
            
            # 清洗和去重
            cleaned_arcs = clean_and_deduplicate_arcs(
                raw_arcs, pin_static_data, config, stats
            )
        else:
            # 标准格式：直接读取，不需要清洗
            print(f"\n  [INFO] Loading standardized arc_delay.json...")
            with open(exported_files['arc_delay'], 'r', encoding='utf-8') as f:
                arc_delay_data = json.load(f)
            cleaned_arcs = arc_delay_data.get('arcs', [])
            print(f"  Loaded {len(cleaned_arcs)} arcs from standardized arc_delay.json")
            
            # 仍然需要解析pin_static（用于后续处理）
            pin_static_data = parse_pin_static_txt(exported_files['pin_static'])
        
        # 生成graph_edges.csv（只允许固定anchor生成权威结构）
        graph_edges_file = static_dir / "graph_edges.csv"
        
        # 只允许固定 anchor 生成权威结构
        STRUCT_ANCHOR = ANCHORS[0]
        is_struct_anchor = (config.corner == STRUCT_ANCHOR)
        
        if not graph_edges_file.exists():
            if not is_struct_anchor:
                raise RuntimeError(
                    f"[STRUCTURE ERROR] {graph_edges_file} not found.\n"
                    f"Graph structure must be generated ONLY by STRUCT_ANCHOR={STRUCT_ANCHOR}.\n"
                    f"Please run corner={STRUCT_ANCHOR} first (for benchmark={config.benchmark})."
                )
            
            # 只有 STRUCT_ANCHOR 才能走生成逻辑
            # 关键修复：graph_edges.csv 必须从 RAW arcs 生成（只做 pin name 合法性过滤）
            # 不能用 cleaned_arcs（清洗会过滤 instance/PI/PO 边，导致 net arcs 丢失）
            # graph_edges 是权威图结构，必须包含所有 cell + net 边
            raw_arcs_for_graph = [
                a for a in raw_arcs
                if is_valid_pin_name(a.get('src', '')) and is_valid_pin_name(a.get('dst', ''))
            ]
            print(f"  [INFO] Generating graph_edges.csv from RAW arcs (before cleaning)")
            print(f"    Raw arcs (valid pins): {len(raw_arcs_for_graph)}")
            cell_raw = sum(1 for a in raw_arcs_for_graph if a.get('edge_type', 0) == 0)
            net_raw = sum(1 for a in raw_arcs_for_graph if a.get('edge_type', 0) == 1)
            print(f"    cell={cell_raw}, net={net_raw}")
            key_to_edge_id = generate_graph_edges_csv(
                raw_arcs_for_graph, graph_edges_file
            )
        else:
            print(f"  [INFO] Using existing graph_edges.csv (generated by STRUCT_ANCHOR={STRUCT_ANCHOR})...")
            # 读取现有的graph_edges.csv
            key_to_edge_id = {}
            with open(graph_edges_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    src = normalize_pin_name(row['src'])
                    dst = normalize_pin_name(row['dst'])
                    edge_type = int(row['edge_type'])
                    edge_id = int(row['edge_id'])
                    key = (src, dst, edge_type)
                    key_to_edge_id[key] = edge_id
            print(f"  Loaded {len(key_to_edge_id)} edges from existing graph_edges.csv")
        
        # 生成node_static.csv（如果不存在则生成，存在则使用现有的）
        # 关键修复：从graph_edges.csv生成，不再依赖arrival
        node_static_file = static_dir / "node_static.csv"
        if not node_static_file.exists():
            print(f"  [INFO] node_static.csv not found, generating from graph_edges.csv...")
            static_pins = generate_node_static_csv_from_structure(
                graph_edges_file, pin_static_data, node_static_file, config
            )
        else:
            print(f"  [INFO] Using existing node_static.csv...")
            # 读取现有的node_static.csv
            static_pins = set()
            node_id_map = {}
            with open(node_static_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pin_name = normalize_pin_name(row['pin_name'])
                    static_pins.add(pin_name)
                    node_id = int(row['node_id'])
                    node_id_map[pin_name] = node_id
            print(f"  Loaded {len(static_pins)} pins from existing node_static.csv")
            
            # 生成或更新node_id_map.json（如果不存在或需要更新）
            node_id_map_file = static_dir / "node_id_map.json"
            if not node_id_map_file.exists() or len(node_id_map) > 0:
                with open(node_id_map_file, 'w', encoding='utf-8') as f:
                    json.dump(node_id_map, f, indent=2, ensure_ascii=False)
                print(f"  Generated/Updated node_id_map.json: {len(node_id_map)} pin_name → node_id mappings")
        
        # 生成arc_delay.json（如果不是标准格式，或需要重新生成）
        if not is_standardized:
            generate_arc_delay_json(cleaned_arcs, key_to_edge_id, corner_dir / "arc_delay.json", config)
            # 删除原始的arc_delay.txt文件（不再需要）
            arc_delay_txt = corner_dir / "arc_delay.txt"
            if arc_delay_txt.exists():
                arc_delay_txt.unlink()
                print(f"  [INFO] Deleted arc_delay.txt (only arc_delay.json is kept)")
        else:
            # 标准格式：直接复制到输出目录（如果不在目标位置）
            # 同时进行基本校验：确保arc_delay.json与graph_edges.csv一致
            output_arc_delay = corner_dir / "arc_delay.json"
            if exported_files['arc_delay'] != output_arc_delay:
                import shutil
                shutil.copy2(exported_files['arc_delay'], output_arc_delay)
                print(f"  [INFO] Copied standardized arc_delay.json to {output_arc_delay.name}")
            else:
                print(f"  [INFO] Standardized arc_delay.json already in target location")
            
            # 删除arc_delay.txt文件（如果存在，不再需要）
            arc_delay_txt = corner_dir / "arc_delay.txt"
            if arc_delay_txt.exists():
                arc_delay_txt.unlink()
                print(f"  [INFO] Deleted arc_delay.txt (only arc_delay.json is kept)")
            
            # 基本校验：检查arc_delay.json中的edge_id是否与graph_edges.csv一致
            if graph_edges_file.exists():
                # 从标准格式的arc_delay.json中提取edge_id集合
                arc_edge_ids = set()
                for arc in cleaned_arcs:
                    eid = arc.get('edge_id')
                    if isinstance(eid, int):
                        arc_edge_ids.add(eid)
                
                # 从graph_edges.csv中提取edge_id集合
                graph_edge_ids = set()
                with open(graph_edges_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        graph_edge_ids.add(int(row['edge_id']))
                
                # 检查是否一致
                if arc_edge_ids != graph_edge_ids:
                    print(f"  [WARNING] arc_delay.json edge_ids ({len(arc_edge_ids)}) != graph_edges.csv edge_ids ({len(graph_edge_ids)})")
                    missing_in_arc = graph_edge_ids - arc_edge_ids
                    extra_in_arc = arc_edge_ids - graph_edge_ids
                    if missing_in_arc:
                        print(f"    Missing in arc_delay.json: {len(missing_in_arc)} edge_ids")
                    if extra_in_arc:
                        print(f"    Extra in arc_delay.json: {len(extra_in_arc)} edge_ids")
                else:
                    print(f"  [OK] Standardized arc_delay.json edge_ids match graph_edges.csv ({len(arc_edge_ids)} edges)")
        
        # 解析并写入标准化的arrival.txt和slew.txt
        # 统一写入到corners目录（每个corner只存一份）
        arrival_data = parse_arrival_txt(exported_files['arrival'])
        slew_data = parse_slew_txt(exported_files['slew'])
        
        # 解析pin_cap（如果存在）
        pin_cap_data = {}
        if 'pin_cap' in exported_files and exported_files['pin_cap'] and exported_files['pin_cap'].exists():
            try:
                pin_cap_data = parse_pin_cap_txt(exported_files['pin_cap'])
            except (PermissionError, OSError, FileNotFoundError) as e:
                print(f"  [WARNING] Could not parse pin_cap.txt: {e}")
                pin_cap_data = {}
        else:
            print("  [WARNING] pin_cap.txt not found (optional but recommended)")
        
        # 解析slack和RAT（如果存在）
        slack_data = {}
        rat_data = {}
        if 'slack' in exported_files and exported_files['slack'] and exported_files['slack'].exists():
            try:
                slack_data = parse_slack_txt(exported_files['slack'])
            except (PermissionError, OSError, FileNotFoundError) as e:
                print(f"  [WARNING] Could not parse slack.txt: {e}")
                slack_data = {}
        
        if 'rat' in exported_files and exported_files['rat'] and exported_files['rat'].exists():
            try:
                rat_data = parse_rat_txt(exported_files['rat'])
            except (PermissionError, OSError, FileNotFoundError) as e:
                print(f"  [WARNING] Could not parse rat.txt: {e}")
                rat_data = {}
        
        # 修复：按static_pins过滤所有pin数据，确保与node_static.csv对齐
        # 避免coverage校验失败（static_pins是过滤后的子集，arrival/slew包含原始全量数据）
        print(f"\n  [INFO] Filtering pin data to align with node_static.csv ({len(static_pins)} pins)...")
        arrival_data_filtered = filter_pin_dict(arrival_data, static_pins)
        slew_data_filtered = filter_pin_dict(slew_data, static_pins)
        pin_cap_data_filtered = filter_pin_dict(pin_cap_data, static_pins) if pin_cap_data else {}
        slack_data_filtered = filter_pin_dict(slack_data, static_pins) if slack_data else {}
        rat_data_filtered = filter_pin_dict(rat_data, static_pins) if rat_data else {}
        
        print(f"    Arrival: {len(arrival_data)} -> {len(arrival_data_filtered)} pins")
        print(f"    Slew: {len(slew_data)} -> {len(slew_data_filtered)} pins")
        if pin_cap_data:
            print(f"    PinCap: {len(pin_cap_data)} -> {len(pin_cap_data_filtered)} pins")
        if slack_data:
            print(f"    Slack: {len(slack_data)} -> {len(slack_data_filtered)} pins")
        if rat_data:
            print(f"    RAT: {len(rat_data)} -> {len(rat_data_filtered)} pins")
        
        # 判断是否为anchor corner（仅用于日志）
        is_anchor = config.corner in ANCHORS
        if is_anchor:
            print(f"\n  [INFO] Corner {config.corner} is an anchor corner")
        
        # 统一写入到corners目录（使用过滤后的数据）
        write_arrival_txt(arrival_data_filtered, corner_dir / "arrival.txt")
        write_slew_txt(slew_data_filtered, corner_dir / "slew.txt")
        
        # 写入过滤后的pin_cap.txt（如果存在）
        if pin_cap_data_filtered:
            write_pin_cap_txt(pin_cap_data_filtered, corner_dir / "pin_cap.txt")
            print(f"  [OK] Wrote pin_cap.txt to corners/{config.corner}/")
        
        # 写入过滤后的slack.txt和rat.txt（如果存在）
        if slack_data_filtered:
            write_slack_txt(slack_data_filtered, corner_dir / "slack.txt")
            print(f"  [OK] Wrote slack.txt to corners/{config.corner}/")
        if rat_data_filtered:
            write_rat_txt(rat_data_filtered, corner_dir / "rat.txt")
            print(f"  [OK] Wrote rat.txt to corners/{config.corner}/")
        
        print(f"  [OK] Wrote arrival.txt and slew.txt to corners/{config.corner}/")
        
        # 生成endpoints.csv（只有slack和rat都存在才生成）
        # 修复：不要用 "or arrival" 触发，因为 endpoints 需要 slack & rat & arrival 的交集
        # 确保 endpoint_pin 必须属于 node_static 的 pin 集合
        if slack_data_filtered and rat_data_filtered:
            generate_endpoints_csv(
                arrival_data_filtered, slack_data_filtered, rat_data_filtered, pin_static_data,
                static_pins, corner_dir / "endpoints.csv", config
            )
        else:
            print(f"  [INFO] Skip endpoints.csv (need both slack and rat, got slack={bool(slack_data_filtered)}, rat={bool(rat_data_filtered)})")
        
        # 不再创建数据划分目录，所有数据统一在corners/目录
        # splits.json会在所有corners处理完后统一生成
        
        # 校验
        validation_results = validate_corner_data(corner_dir, static_dir, config, stats)
        
        # 生成meta.json（分离静态和corner特定数据）
        meta_file = generate_meta_json(static_dir, corner_dir, config, stats, validation_results)
        
        # 检查是否有错误
        if validation_results.get('errors'):
            print("\n" + "=" * 60)
            print("[WARNING] Validation found errors:")
            for error in validation_results['errors']:
                print(f"  - {error}")
            print("=" * 60)
        
        print("\n" + "=" * 80)
        print(f"[OK] Processing complete: {config.benchmark} / {config.corner}")
        print("=" * 80)
        
        return {
            'success': True,
            'stats': stats,
            'validation': validation_results
        }
        
    except Exception as e:
        print(f"\n[ERROR] Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


def main():
    parser = argparse.ArgumentParser(
        description='通用数据导出与标准化脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 处理单个benchmark的单个corner
  python export_and_standardize_data.py --benchmark gcd --corner tt0p85v25c

  # 处理单个benchmark的所有corners
  python export_and_standardize_data.py --benchmark gcd --all-corners

  # 处理所有benchmarks的所有corners
  python export_and_standardize_data.py --all-benchmarks --all-corners
        """
    )
    
    parser.add_argument('--benchmark', type=str, choices=ALL_BENCHMARKS,
                       help='Benchmark名称')
    parser.add_argument('--all-benchmarks', action='store_true',
                       help='处理所有benchmarks')
    parser.add_argument('--corner', type=str,
                       help='Corner名称')
    parser.add_argument('--all-corners', action='store_true',
                       help='处理所有corners')
    parser.add_argument('--benchmark-root', type=str,
                       default='D:/bishe_database/benchmark',
                       help='Benchmark根目录')
    parser.add_argument('--opentimer-path', type=str,
                       default='D:/opentimer/OpenTimer',
                       help='OpenTimer路径')
    parser.add_argument('--lib-path-template', type=str,
                       default='D:/bishe_database/BUFLIB/lib_rvt/saed32rvt_{corner}.lib',
                       help='库文件路径模板（使用{corner}占位符）')
    parser.add_argument('--netlist-path-template', type=str,
                       default='D:/bishe_database/benchmark/netlists/{benchmark}/{benchmark}_netlist.v',
                       help='Netlist路径模板（使用{benchmark}占位符）')
    parser.add_argument('--sdc-path-template', type=str,
                       default='D:/bishe_database/benchmark/netlists/{benchmark}/{benchmark}.sdc',
                       help='SDC路径模板（使用{benchmark}占位符）')
    parser.add_argument('--output-root', type=str,
                       default='D:/bishe_database/benchmark/test_output',
                       help='输出根目录')
    parser.add_argument('--keep-pi-po', dest='keep_pi_po', action='store_true', default=True,
                       help='保留PI/PO节点（默认开启）')
    parser.add_argument('--no-keep-pi-po', dest='keep_pi_po', action='store_false',
                       help='不保留PI/PO节点')
    # 修复C1: 统一参数语义，默认不保留instance body（符合规范）
    parser.add_argument('--keep-instance', dest='keep_instance', action='store_true', default=False,
                       help='保留instance节点（默认不保留）')
    parser.add_argument('--no-keep-instance', dest='keep_instance', action='store_false',
                       help='不保留instance节点（默认行为）')
    parser.add_argument('--opentimer-version', type=str,
                       help='OpenTimer版本（将写入meta.json）')
    parser.add_argument('--skip-opentimer', action='store_true',
                       help='跳过OpenTimer导出，直接使用现有数据')
    parser.add_argument('--existing-data-dir', type=str,
                       help='现有数据目录（当--skip-opentimer时使用）')
    parser.add_argument('--keep-tcl', action='store_true',
                       help='保留TCL文件（默认删除，debug时保留）')
    
    args = parser.parse_args()
    
    # 确定要处理的benchmarks和corners
    if args.all_benchmarks:
        benchmarks = ALL_BENCHMARKS
    elif args.benchmark:
        benchmarks = [args.benchmark]
    else:
        parser.error("必须指定--benchmark或--all-benchmarks")
    
    if args.all_corners:
        corners = ALL_CORNERS
    elif args.corner:
        corners = [args.corner]
    else:
        parser.error("必须指定--corner或--all-corners")
    
    # 关键：保证结构 anchor 先跑
    def reorder_corners_with_struct_anchor_first(corners: List[str]) -> List[str]:
        """重排序corners，确保STRUCT_ANCHOR先跑"""
        struct_anchor = ANCHORS[0]
        if struct_anchor in corners:
            return [struct_anchor] + [c for c in corners if c != struct_anchor]
        return corners
    
    corners = reorder_corners_with_struct_anchor_first(list(corners))
    
    # 处理每个benchmark和corner
    results = []
    for benchmark in benchmarks:
        for corner in corners:
            existing_data_dir = None
            if args.skip_opentimer:
                if args.existing_data_dir:
                    existing_data_dir = Path(args.existing_data_dir)
                else:
                    # 从新的数据结构查找（corners/{corner}/）
                    new_data_dir = Path(args.output_root) / benchmark / "corners" / corner
                    if new_data_dir.exists():
                        existing_data_dir = new_data_dir
                        print(f"  [INFO] Found existing data at: {new_data_dir}")
                    else:
                        raise ValueError(
                            f"--skip-opentimer specified but no existing data found. "
                            f"Please specify --existing-data-dir or ensure data exists at {new_data_dir}"
                        )
            
            config = Config(
                benchmark=benchmark,
                corner=corner,
                benchmark_root=Path(args.benchmark_root),
                opentimer_path=Path(args.opentimer_path),
                lib_path_template=args.lib_path_template,
                netlist_path_template=args.netlist_path_template,
                sdc_path_template=args.sdc_path_template,
                output_root=Path(args.output_root),
                keep_pi_po=args.keep_pi_po,
                keep_instance=args.keep_instance,
                opentimer_version=args.opentimer_version,
                skip_opentimer=args.skip_opentimer,
                existing_data_dir=existing_data_dir,
                keep_tcl=args.keep_tcl
            )
            
            result = process_single_corner(config)
            results.append({
                'benchmark': benchmark,
                'corner': corner,
                'result': result
            })
    
    # 打印总结
    print("\n" + "=" * 80)
    print("Processing Summary")
    print("=" * 80)
    
    success_count = sum(1 for r in results if r['result'].get('success'))
    total_count = len(results)
    
    print(f"\nTotal: {total_count} benchmark-corner combinations")
    print(f"Success: {success_count}")
    print(f"Failed: {total_count - success_count}")
    
    if success_count < total_count:
        print("\nFailed combinations:")
        for r in results:
            if not r['result'].get('success'):
                print(f"  {r['benchmark']}/{r['corner']}: {r['result'].get('error', 'Unknown error')}")
    
    # 为每个benchmark生成splits.json
    print("\n" + "=" * 80)
    print("Generating splits.json")
    print("=" * 80)
    for benchmark in set(r['benchmark'] for r in results):
        output_root = Path(args.output_root)
        splits_file = generate_splits_json(output_root, benchmark)
        print(f"  [OK] Generated splits.json for {benchmark}: {splits_file}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

