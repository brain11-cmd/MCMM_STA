# 通用数据导出与标准化脚本

## 概述

`export_and_standardize_data.py` 是一个通用的数据导出与标准化脚本，支持12个benchmark和27个corners的数据处理。

## 核心功能

### 三步处理流程

1. **Step1: OpenTimer导出**
   - 运行OpenTimer导出原始dump文件
   - 导出文件：arrival.txt, slew.txt, pin_cap.txt, pin_static.txt, net_load.txt, arc_delay.txt/json

2. **Step2: 解析+清洗**
   - 解析原始dump文件
   - 过滤无效pin name
   - 过滤instance节点（可选）
   - 按(src, dst, edge_type)分组去重
   - 应用选优规则（规则A/B/C）
   - 修复Net arc的mask规则

3. **Step3: 标准化输出+校验**
   - 生成graph_edges.csv（权威边定义）
   - 生成node_static.csv
   - 生成arc_delay.json（按edge_id对齐）
   - 生成标准化的arrival.txt和slew.txt
   - 执行校验（pin coverage、edge coverage、hash校验、数值sanity）
   - 生成meta.json

## 满足的要求

### A. 输入一致性与版本控制
- ✅ 同一benchmark的所有corner使用同一套netlist+SDC
- ✅ Pin name规范化函数全局唯一
- ✅ 单位统一（固定为ns）
- ✅ meta.json记录OpenTimer版本

### B. 权威结构定义
- ✅ graph_edges.csv是权威边定义，只生成一次
- ✅ 所有corner的arc_delay按edge_id填值
- ✅ edge_id连续（0..E-1）

### C. 节点集合与过滤规则
- ✅ 训练图是pin-only：过滤__INSTANCE__节点
- ✅ 过滤无效pin name（如_387_:）
- ✅ PI/PO处理（可选保留）

### D. 重复边与占位符
- ✅ 确定性选优策略消歧
- ✅ 选优顺序：valid通道非零数最多 → sum(delay)最大 → 取第一条
- ✅ 全0占位符优先丢弃
- ✅ 统计输出：conflict_groups_ratio、all_zero_ratio

### E. Net arc的通道与mask
- ✅ Cell arc：mask=[1,1,1,1]
- ✅ Net arc：固定mask=[1,0,0,1]（RF/FR永远无效）

### F. Corner输出文件规范
- ✅ static/（每benchmark一份）
  - node_static.csv
  - graph_edges.csv
  - meta.json
- ✅ corners/<corner>/（每corner一份）
  - arrival.txt
  - slew.txt
  - arc_delay.json
  - （可选）slack.txt或rat.txt

### G. 必做校验
- ✅ pin coverage：≥99.9%
- ✅ edge coverage：≥99.9%
- ✅ hash校验：同benchmark不同corner的graph_edges.csv hash一致
- ✅ 数值sanity：delay/arrival/slew不应全为0

### H. 训练样本生成
- ✅ 输出最小集合：static/node_static.csv, static/graph_edges.csv, corners/<corner>/arrival,slew,arc_delay

### I. 通用参数化设计
- ✅ 参数化：benchmark_root、corner_name、OpenTimer路径、lib/netlist/sdc路径模板
- ✅ pin normalize规则（单独函数）
- ✅ 过滤规则开关（是否保留PI/PO、是否保留INSTANCE）

## 使用方法

### 基本用法

```bash
# 处理单个benchmark的单个corner
python export_and_standardize_data.py --benchmark gcd --corner tt0p85v25c

# 处理单个benchmark的所有corners
python export_and_standardize_data.py --benchmark gcd --all-corners

# 处理所有benchmarks的所有corners
python export_and_standardize_data.py --all-benchmarks --all-corners
```

### 参数说明

#### 必需参数
- `--benchmark BENCHMARK`: 指定benchmark名称（或使用`--all-benchmarks`）
- `--corner CORNER`: 指定corner名称（或使用`--all-corners`）

#### 可选参数
- `--benchmark-root PATH`: Benchmark根目录（默认：`D:/bishe_database/benchmark`）
- `--opentimer-path PATH`: OpenTimer路径（默认：`D:/opentimer/OpenTimer`）
- `--lib-path-template TEMPLATE`: 库文件路径模板（默认：`D:/bishe_database/BUFLIB/lib_rvt/saed32rvt_{corner}.lib`）
- `--netlist-path-template TEMPLATE`: Netlist路径模板（默认：`D:/bishe_database/benchmark/netlists/{benchmark}/{benchmark}_netlist.v`）
- `--sdc-path-template TEMPLATE`: SDC路径模板（默认：`D:/bishe_database/benchmark/netlists/{benchmark}/{benchmark}.sdc`）
- `--output-root PATH`: 输出根目录（默认：`D:/bishe_database/benchmark/test_output`）
- `--keep-pi-po`: 保留PI/PO节点（默认：True）
- `--no-keep-instance`: 不保留instance节点（默认：保留）
- `--opentimer-version VERSION`: OpenTimer版本（将写入meta.json）

### 路径模板说明

路径模板支持占位符：
- `{benchmark}`: 将被替换为benchmark名称
- `{corner}`: 将被替换为corner名称

例如：
```bash
--lib-path-template "D:/libs/saed32rvt_{corner}.lib"
--netlist-path-template "D:/netlists/{benchmark}/{benchmark}.v"
```

## 输出目录结构

```
output_root/
├── <benchmark>/
│   ├── static/
│   │   ├── node_static.csv      # 节点静态信息（每benchmark一份）
│   │   ├── graph_edges.csv      # 权威边定义（每benchmark一份）
│   │   └── meta.json            # 元数据（版本、单位、统计信息）
│   └── corners/
│       ├── <corner1>/
│       │   ├── arrival.txt      # Arrival time
│       │   ├── slew.txt         # Slew
│       │   └── arc_delay.json   # Arc delay（按edge_id对齐）
│       ├── <corner2>/
│       │   └── ...
│       └── ...
```

## 处理流程详解

### Step1: OpenTimer导出

脚本会：
1. 构建库文件、netlist、SDC路径
2. 检查文件存在性
3. 生成TCL脚本
4. 通过WSL运行OpenTimer
5. 检查导出的文件

**注意**：如果`dump_arc_delay`命令未实现，脚本会尝试从现有的arc_delay.json读取。

### Step2: 解析+清洗

1. **过滤无效pin name**
   - 过滤空pin name
   - 过滤格式错误的pin name（如`_387_:`这种没有pin名的）

2. **过滤instance节点**（如果`--no-keep-instance`）
   - 过滤以`:`结尾且无pin_role的节点

3. **分组去重**
   - 按`(src, dst, edge_type)`分组
   - 应用选优规则：
     - 规则A：valid通道非零数最多
     - 规则B：sum(delay)最大
     - 规则C：全0占位符优先丢弃

4. **修复Net arc mask**
   - Net arc：固定mask=[1,0,0,1]
   - Cell arc：保持原mask

### Step3: 标准化输出+校验

1. **生成graph_edges.csv**
   - 权威边定义
   - edge_id连续（0..E-1）
   - 只在第一个corner时生成（或不存在时）

2. **生成node_static.csv**
   - 从arrival.txt和pin_static.txt合并
   - 只在第一个corner时生成（或不存在时）

3. **生成arc_delay.json**
   - 按edge_id对齐
   - 每个corner都生成

4. **校验**
   - Pin coverage：≥99.9%
   - Edge coverage：≥99.9%
   - Hash校验：graph_edges.csv hash一致
   - 数值sanity：检查非零值

5. **生成meta.json**
   - 记录版本、单位、统计信息、校验结果

## 注意事项

1. **输入一致性**
   - 确保同一benchmark的所有corner使用同一套netlist+SDC
   - 任何netlist/SDC改动都会改变pin/edge集合

2. **graph_edges.csv唯一性**
   - graph_edges.csv是权威边定义，只生成一次
   - 所有corner的arc_delay必须按edge_id填值

3. **覆盖率要求**
   - Pin coverage和edge coverage必须≥99.9%
   - 否则会报错停止

4. **cell_all_zero_ratio报警**
   - 如果cell_all_zero_ratio > 5%，会报警
   - 通常是没update_timing或库没生效

5. **OpenTimer版本**
   - 建议通过`--opentimer-version`指定版本
   - 版本信息会写入meta.json

## 故障排除

### OpenTimer导出失败
- 检查OpenTimer路径是否正确
- 检查库文件、netlist、SDC文件是否存在
- 检查WSL是否可用

### 覆盖率不足
- 检查是否所有corner使用同一套netlist+SDC
- 检查pin name规范化是否一致
- 检查是否有instance节点过滤问题

### arc_delay缺失
- 如果`dump_arc_delay`命令未实现，脚本会尝试从现有JSON读取
- 确保至少有一个corner有完整的arc_delay数据

## 示例

### 示例1：处理单个corner

```bash
python export_and_standardize_data.py \
    --benchmark gcd \
    --corner tt0p85v25c \
    --opentimer-version "v1.0.0"
```

### 示例2：处理所有corners

```bash
python export_and_standardize_data.py \
    --benchmark gcd \
    --all-corners \
    --opentimer-version "v1.0.0"
```

### 示例3：自定义路径

```bash
python export_and_standardize_data.py \
    --benchmark gcd \
    --corner tt0p85v25c \
    --lib-path-template "D:/custom/libs/saed32rvt_{corner}.lib" \
    --netlist-path-template "D:/custom/netlists/{benchmark}/{benchmark}.v" \
    --output-root "D:/custom/output"
```

## 相关文件

- `数据划分方案.md`: 数据划分方案（Train/Val/Test/Anchors）
- `canonicalize_arc_delay_json.py`: Arc delay规范化脚本
- `regenerate_graph_edges_canonical.py`: Graph edges重新生成脚本






















