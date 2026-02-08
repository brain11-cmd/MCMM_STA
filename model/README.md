# Physics-Informed Multi-Anchor GNN STA

> 从 3 个 anchor corner 的时序数据，预测任意 target corner 的 edge delay，并通过可微 STA 传播得到 endpoint slack。

---

## 目录结构

```
model/
├── configs/
│   └── base.yaml            # 全部超参数配置
├── data/
│   ├── dataset.py           # 数据集：读取导出数据，组装训练样本
│   ├── collate.py           # DataLoader 的 batch 拼接函数
│   └── normalization.py     # 特征 z-score 标准化
├── models/
│   ├── gnn.py               # GraphSAGE + LogSumExp 聚合
│   ├── edge_head.py         # 边特征构造 + MLP
│   ├── multi_anchor.py      # 多锚点延迟生成（两级 gating）
│   ├── sta.py               # 可微 STA（smooth max-plus 传播）
│   └── full_model.py        # 完整模型 pipeline
├── losses/
│   └── losses.py            # 4 项复合损失函数
├── utils/
│   ├── io.py                # 数据文件 I/O（读 csv/json/txt）
│   ├── seed.py              # 随机种子
│   ├── metrics.py           # 评估指标（MAE/RMSE/R²）
│   ├── checkpoint.py        # 模型保存/加载
│   └── sanity_checks.py     # 启动前数据自检
├── train.py                 # 训练入口
└── eval.py                  # 评估入口
```

---

## 快速开始

### 1. 依赖

```
Python >= 3.10
PyTorch >= 2.0
pyyaml, numpy, pandas, tqdm
```

### 2. 数据准备

数据由 `benchmark/scripts/core/31号凌晨批量版.py` 导出，存放在 `benchmark/test_output/` 下：

```
test_output/{benchmark}/
├── static/
│   ├── graph_edges.csv      # 权威边定义 (edge_id, src, dst, edge_type)
│   ├── node_static.csv      # 节点静态特征 (node_id, pin_name, fanin, fanout, cell_type, pin_role)
│   └── node_id_map.json     # pin_name → node_id 映射
├── corners/{corner_name}/
│   ├── arc_delay.json       # 边延迟 [E, 4] + mask + edge_valid
│   ├── arrival.txt          # 到达时间 (E/R, E/F, L/R, L/F)
│   ├── slew.txt             # 转换时间
│   ├── pin_cap.txt          # 引脚电容
│   ├── slack.txt            # 松弛量
│   ├── rat.txt              # Required Arrival Time
│   └── endpoints.csv        # endpoint slack/RAT 标签
└── splits.json              # 数据划分 (anchors / train / val / test)
```

需要确保 **3 个 anchor corner** 和至少部分 **target corner** 已导出。

### 3. 训练

```bash
cd D:\bishe_database\model
python train.py --config configs/base.yaml
```

常用参数覆盖：
```bash
python train.py --config configs/base.yaml --epochs 100 --lr 1e-4 --device cpu
```

### 4. 评估

```bash
python eval.py --config configs/base.yaml --checkpoint checkpoints/best.pt --split test
```

---

## 模型架构

### 整体流水线

```
┌──────────────────────────────────────────────────────────────┐
│  输入                                                         │
│  ├── pin 静态特征: [log1p(fanin), log1p(fanout)]              │
│  ├── K=3 个 anchor 的 arrival/slew: [K, N, 4]                │
│  ├── K=3 个 anchor 的 edge delay:   [K, E, 4]                │
│  └── target corner 条件向量 z_t:    [5]                       │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
         ┌─────────────────────────┐
         │  1. GraphSAGE Encoder   │  3 层, hidden=128
         │     LogSumExp 聚合       │  残差连接
         │     → h_v [N, 128]      │
         └────────────┬────────────┘
                      ▼
         ┌─────────────────────────┐
         │  2. Edge Head           │  对每条边 e=(u→v):
         │     [h_u, h_v,          │  [h_u, h_v, h_u*h_v, |h_u-h_v|]
         │      h_u*h_v, |h_u-h_v| │  + emb(edge_type, cell_type, pin_role)
         │      + embeddings       │  + scalar(fanin, fanout, cap)
         │      + scalars]         │  → MLP → h_e [E, 128]
         │     → h_e [E, 128]     │
         └────────────┬────────────┘
                      ▼
         ┌─────────────────────────┐
         │  3. Multi-Anchor Head   │  核心创新：
         │     Scale MLP           │  s_hat = exp(MLP([h_e, z_t]))
         │     Two-level Gating    │  gG = softmax(MLP(z_t))        全局
         │     → d_hat [E, 4]     │  lL = MLP([h_e, z_t])          局部
         │                         │  g_e = softmax(log(gG) + β·lL)
         │                         │  d_hat = Σ_k g_e[k]·s_hat[k]·d_anchor[k]
         └────────────┬────────────┘
                      ▼
         ┌─────────────────────────┐
         │  4. Differentiable STA  │  按拓扑序传播:
         │     smooth max-plus     │  AT[v,R] = smoothmax{AT[u,R]+d[RR], AT[u,F]+d[FR]}
         │     → AT [N, 2]        │  AT[v,F] = smoothmax{AT[u,R]+d[RF], AT[u,F]+d[FF]}
         │     → slack [M, 2]     │  slack = RAT_true - AT_hat
         └────────────────────────┘
```

### 各模块详解

#### `models/gnn.py` — GraphSAGE + LogSumExp

每层操作：
1. 对每个节点 v，用 LogSumExp 聚合所有邻居 u 的特征（数值稳定，带温度 τ）
2. 拼接 `[self_feat ‖ agg_feat]`
3. 线性变换 → LayerNorm → ReLU → Dropout
4. 残差连接：`h = h + h_new`

LogSumExp 聚合的数值稳定实现（纯 PyTorch，不依赖 torch_scatter）：
```
m = max(x_i / τ)
out = τ × (m + log(Σ exp(x_i/τ - m)))
```

#### `models/edge_head.py` — 边特征头

对每条边 `e = (u → v)` 构造特征向量：
- **节点交互**: `[h_u, h_v, h_u⊙h_v, |h_u − h_v|]` → 4×128 = 512 维
- **类别嵌入**: `emb(edge_type) + emb(cell_type_u) + emb(cell_type_v) + emb(pin_role_u) + emb(pin_role_v)` → 5×16 = 80 维
- **标量特征**: `[log1p(fanin_u), log1p(fanout_u), log1p(fanin_v), log1p(fanout_v), log1p(cap_u), log1p(cap_v)]` → 6 维

总计 598 维 → 3 层 MLP → 128 维边嵌入 `h_e`

#### `models/multi_anchor.py` — 多锚点延迟生成

对每条边 e、每个通道 c∈{RR,RF,FR,FF}、每个 anchor k∈{0,1,2}：

1. **Scale 预测**: `Δ = MLP_scale([h_e, z_t])` → `s_hat = exp(clamp(Δ, -3, 3))`
2. **两级 Gating**:
   - 全局: `gG = softmax(MLP_g(z_t))` — 只看 corner 条件，所有边共享
   - 局部: `lL = MLP_l([h_e, z_t])` — 每条边不同
   - 融合: `g_e = softmax(log(gG) + β·lL)` — β 控制局部权重的锐度
3. **延迟融合**: `d_hat[e,c] = Σ_k g_e[k] × s_hat[e,k,c] × d_anchor[k][e,c]`

物理含义：target corner 的延迟 ≈ 对 3 个 anchor 延迟做"加权缩放"，缩放系数和权重都是学出来的。

#### `models/sta.py` — 可微 STA

按拓扑序逐节点传播 arrival time：

```
对每个节点 v（按拓扑序）:
  AT[v, Rise] = smoothmax({AT[u,R] + d[e,RR], AT[u,F] + d[e,FR]})
  AT[v, Fall] = smoothmax({AT[u,R] + d[e,RF], AT[u,F] + d[e,FF]})
```

其中 `smoothmax` 是 LogSumExp 近似 max（温度 τ=0.07，越小越接近 hard max）：
```
smoothmax(x₁,...,xₙ) = m + τ·log(Σ exp((xᵢ-m)/τ))    其中 m = max(xᵢ)
```

提供两种实现：
- `DifferentiableSTA`: 逐节点循环，精确但慢
- `VectorizedSTA`: 按拓扑层级向量化，快但稍有近似

#### `models/full_model.py` — 完整模型

串联上述 4 个模块，额外包含一个 `input_arrival_head`：
- 用 anchor 的 arrival + z_t 预测 STA 传播的初始 arrival（源节点）
- 输出 `ModelOutput` 包含所有中间结果（d_hat, AT, slack, gating weights）

---

## 损失函数

`losses/losses.py` 中定义了 4 项复合损失：

| 损失项 | 公式 | 作用 | 默认权重 |
|--------|------|------|----------|
| **L_slack** | Huber(slack_hat − slack_true) | 主监督：endpoint slack 精度 | 1.0 |
| **L_edge** | Huber(log1p(d_hat) − log1p(d_true)) × mask | 边延迟精度（log 空间） | λ=0.3 |
| **L_KL** | KL(g_e ‖ gG) | gating 正则：局部不偏离全局太远 | λ=0.01 |
| **L_ent** | −H(g_e) = Σ g_e·log(g_e) | 熵正则：防止 gating 坍缩到单一 anchor | λ=0.001 |

**总损失**: `L = L_slack + 0.3·L_edge + 0.01·L_KL + 0.001·L_ent`

关键设计：
- L_edge 在 **log1p 空间**计算，避免大延迟主导梯度
- L_edge 只对 **edge_valid=1 且 mask=1** 的通道计算
- L_slack 使用 Huber loss（δ=1.0），对异常值鲁棒

---

## 数据流

### 训练样本定义

一个样本 = **(benchmark, target_corner)**，包含：

| 字段 | 形状 | 来源 |
|------|------|------|
| `pin_static` | [N, 2] | node_static.csv → log1p(fanin/fanout) |
| `pin_dyn_anchor` | [K=3, N, 4] | anchor corners 的 arrival_LR/LF + slew_LR/LF |
| `d_anchor` | [K=3, E, 4] | anchor corners 的 arc_delay (dRR/dRF/dFR/dFF) |
| `d_target_true` | [E, 4] | target corner 的 arc_delay（标签） |
| `mask` | [E, 4] | 通道有效性（net 的 RF/FR 永远=0） |
| `edge_valid` | [E] | 边整体有效性（0=缺失边） |
| `endpoint_ids` | [M] | endpoint 的 node_id |
| `slack_true` | [M, 2] | endpoint slack 标签 (LateR, LateF) |
| `rat_true` | [M, 2] | Required Arrival Time（用于 slack = RAT − AT） |
| `z_t` | [5] | target corner 条件向量 [process_id, V, T, V_norm, T_norm] |

### Corner 条件编码

corner 名称自动解析为条件向量 z_t：
```
"ff0p85vn40c" → process=ff(0), voltage=0.85, temp=-40
z_t = [0.0, 0.85, -40.0, 0.0, -0.8125]
       │     │      │      │     └── (temp-25)/80
       │     │      │      └── (voltage-0.85)/0.2
       │     │      └── 原始温度
       │     └── 原始电压
       └── process_id (ff=0, tt=1, ss=2)
```

---

## 训练流程

`train.py` 的完整流程：

```
1. 加载配置 (base.yaml + CLI 覆盖)
2. 设置随机种子
3. 运行 sanity checks:
   ├── 检查 graph_edges 与 arc_delay 边数一致
   ├── 检查 net arc 的 RF/FR mask = 0
   ├── 计算拓扑排序（检测是否有环）
   └── 检查 anchor 数据完整性
4. 加载 splits.json → 确定 train/val/test corners
5. 构建 Dataset + DataLoader
6. 计算特征标准化统计量（扫一遍训练集）
7. 构建模型 + 优化器 + 调度器
8. 训练循环:
   ├── train_one_epoch: forward → loss → backward → clip_grad → step
   ├── evaluate: val_slack_mae / val_edge_mae
   ├── 保存 best checkpoint (按 val_slack_mae)
   ├── Cosine annealing scheduler
   └── Early stopping (patience=30)
9. 输出最终结果
```

---

## 超参数配置

`configs/base.yaml` 中的关键超参：

### 模型
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `gnn_layers` | 3 | GraphSAGE 层数 |
| `hidden_dim` | 128 | 隐藏维度 |
| `tau_sage` | 1.0 | SAGE 聚合的 LogSumExp 温度 |
| `edge_mlp_layers` | 3 | Edge MLP 层数 |
| `edge_mlp_hidden` | 256 | Edge MLP 隐藏维度 |
| `beta` | 1.0 | 局部 gating 锐度 |
| `scale_clamp` | 3.0 | log-scale 裁剪范围 [-3, 3] |
| `tau_sta` | 0.07 | STA smoothmax 温度 |

### 训练
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `epochs` | 200 | 最大训练轮数 |
| `lr` | 3e-4 | 学习率 |
| `weight_decay` | 1e-5 | L2 正则 |
| `batch_size` | 1 | 每步处理的图数量 |
| `grad_clip` | 5.0 | 梯度裁剪 |
| `scheduler` | cosine | 学习率调度 (cosine/step/none) |
| `patience` | 30 | Early stopping 耐心值 |

### 损失权重
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `huber_delta` | 1.0 | Huber 损失的 δ |
| `lambda_edge` | 0.3 | 边延迟损失权重 |
| `lambda_kl` | 0.01 | KL 正则权重 |
| `lambda_ent` | 0.001 | 熵正则权重 |

---

## 数据划分

基于 `splits.json`：

| 划分 | 数量 | 说明 |
|------|------|------|
| **Anchors** | 3 | ff1p16vn40c, tt0p85v25c, ss0p7v25c — 只做输入特征 |
| **Train targets** | 12 | vn40c/25c 温度的 corners（排除 anchors） |
| **Val targets** | 3 | ff0p95v25c, ss0p75vn40c, tt1p05v25c |
| **Test targets** | 9 | 全部 125°C corners — 完全未见过的温度 |

---

## 文件详细说明

### `configs/base.yaml`

所有超参数的唯一来源。训练和评估脚本都从这里读取配置，支持 CLI 覆盖。

### `data/dataset.py`

- **`BenchmarkStatic`**: 每个 benchmark 的静态数据（图结构、节点特征、词表），加载一次后缓存
- **`STADataset`**: PyTorch Dataset，每个样本 = (benchmark, target_corner)
  - 初始化时缓存所有 anchor 数据（避免重复 IO）
  - `__getitem__` 加载 target corner 数据，组装成 `STASample`
- **`corner_to_condition()`**: 将 corner 名称解析为 5 维条件向量

### `data/collate.py`

- batch_size=1 时直接透传
- batch_size>1 时做 block-diagonal 图拼接（node/edge id 加偏移量）

### `data/normalization.py`

- 训练前扫一遍数据，统计每个特征的 mean/std
- 训练时做 z-score: `x_norm = (x - mean) / std`
- mean/std 保存到 checkpoint，推理时加载复用

### `models/gnn.py`

- `scatter_logsumexp()`: 纯 PyTorch 实现的 LogSumExp scatter 聚合
- `GraphSAGELayer`: 单层 SAGE（聚合 + 线性 + LayerNorm + ReLU）
- `GraphSAGEEncoder`: 多层 SAGE + 残差连接

### `models/edge_head.py`

- 5 种类别嵌入（edge_type, cell_type×2, pin_role×2）
- 4 种节点交互（h_u, h_v, h_u⊙h_v, |h_u−h_v|）
- 6 个标量特征（log1p 变换）
- 3 层 MLP → 128 维边嵌入

### `models/multi_anchor.py`

- `scale_mlp`: 预测 K×4 个 log-scale 因子
- `global_gate`: z_t → K 维 softmax（全局权重）
- `local_gate`: [h_e, z_t] → K 维 logits（局部权重）
- 融合公式: `d_hat = Σ_k softmax(log(gG)+β·lL)[k] × exp(Δ)[k] × d_anchor[k]`

### `models/sta.py`

- `smoothmax()`: 单次 LogSumExp，带 max-subtract 数值稳定
- `DifferentiableSTA`: 逐节点拓扑传播（精确，适合小图）
- `VectorizedSTA`: 按拓扑层级向量化（快速，适合大图）

### `models/full_model.py`

- 串联 GNN → EdgeHead → MultiAnchor → STA
- `input_arrival_head`: 从 anchor arrivals + z_t 预测初始 arrival
- 返回 `ModelOutput`（d_hat, AT, slack, gating weights）

### `losses/losses.py`

- 4 项损失的实现，返回 dict 方便日志记录
- L_edge 在 log1p 空间计算，乘 mask 和 edge_valid

### `utils/io.py`

- 读取所有导出文件的函数
- `parse_corner_name()`: 正则解析 corner 名称

### `utils/sanity_checks.py`

- 启动前自检：边数一致性、mask 规则、拓扑排序、anchor 完整性
- `compute_topo_order()`: Kahn 算法拓扑排序

### `utils/metrics.py`

- `slack_metrics()`: MAE / RMSE / R²
- `edge_delay_metrics()`: 带 mask 的 MAE / RMSE

### `utils/checkpoint.py`

- 保存：model + optimizer + epoch + best_metric + norm_stats
- 加载：支持 resume 训练

### `utils/seed.py`

- 设置 Python / NumPy / PyTorch 全部随机种子








