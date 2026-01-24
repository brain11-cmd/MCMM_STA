# Benchmark OpenTimer 运行状态（更新）

## ✅ 可以运行的 Benchmark（8个）

| Benchmark | 状态 | WNS | 最差路径延迟 | 备注 |
|-----------|------|-----|------------|------|
| **gcd** | ✅ 正常 | 0.075 ns | ~0.9 ns | 已优化到 1.0 ns |
| **uart** | ✅ 正常 | 0.038 ns | ~0.15 ns | 已优化到 0.15 ns |
| **spi** | ✅ 正常 | 0.019 ns | ~0.15 ns | 已优化到 0.15 ns |
| **aes** | ✅ 正常 | 0.004 ns | ~0.096 ns | 已优化到 0.1 ns |
| **dynamic_node** | ✅ 正常 | 0.019 ns | ~3.5 ns | 可优化到 ~3.5 ns |
| **fifo** | ✅ 可运行 | -30.6106 ns | - | 时序未收敛（TNS -979.349） |
| **jpeg** | ✅ 可运行 | -0.1146 ns | - | 时序未收敛（TNS -7.2654） |
| **ethmac** | ✅ 可运行 | -0.0688 ns | - | 时序未收敛（TNS -78.2712） |

## ⚠️ 仍需优化的 Benchmark（3个）

### fifo
- **状态**: ✅ 可运行，但时序未收敛
- **问题**: WNS/TNS 为负值，当前约束下存在较大时序违例

### jpeg
- **状态**: ✅ 可运行，但时序未收敛
- **问题**: WNS/TNS 为负值，仍需进一步优化

### ethmac
- **状态**: ✅ 可运行，但时序未收敛
- **问题**: WNS/TNS 为负值，仍需进一步优化

## 修复工具

### fix_ports.py
- 修复简单转义标识符：`\name[index]` → `name_index`
- 修复复杂转义标识符：`\name.subname[index]` → `name_subname_index`

### fix_isolation_cells.py
- 替换 ISOLANDX1_RVT → INVX0_RVT + AND2X1_RVT
- 替换 ISOLORX1_RVT → OR2X1_RVT

## 当前可用 Benchmark

**8个 benchmark 可以正常运行 OpenTimer：**
1. gcd (1.0 ns, 1000 MHz)
2. uart (0.15 ns, 6667 MHz)
3. spi (0.15 ns, 6667 MHz)
4. aes (0.1 ns, 10000 MHz)
5. dynamic_node (10 ns, 100 MHz，可优化)

这些 benchmark 已经足够用于：
- ✅ GNN 数据提取
- ✅ 多 corner 时序分析（27 个 PVT corners）
- ✅ 图结构特征提取

## 下一步建议

对于 fifo, jpeg, ethmac：
1. **选项1**: 调整 SDC 时钟约束，降低频率以收敛时序
2. **选项2**: 重新综合，优化关键路径
3. **选项3**: 继续用当前结果进行图特征提取/时序分析
