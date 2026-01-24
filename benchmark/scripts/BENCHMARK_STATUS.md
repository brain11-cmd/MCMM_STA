# Benchmark OpenTimer 运行状态（更新）

## ✅ 可以运行的 Benchmark（5个）

| Benchmark | 状态 | WNS | 最差路径延迟 | 备注 |
|-----------|------|-----|------------|------|
| **gcd** | ✅ 正常 | 0.075 ns | ~0.9 ns | 已优化到 1.0 ns |
| **uart** | ✅ 正常 | 0.038 ns | ~0.15 ns | 已优化到 0.15 ns |
| **spi** | ✅ 正常 | 0.019 ns | ~0.15 ns | 已优化到 0.15 ns |
| **aes** | ✅ 正常 | 0.004 ns | ~0.096 ns | 已优化到 0.1 ns |
| **dynamic_node** | ✅ 正常 | 0.019 ns | ~3.5 ns | 可优化到 ~3.5 ns |

## ⚠️ 部分修复的 Benchmark（3个）

### 1. fifo
- **状态**: ⚠️ 转义标识符已修复，但隔离单元问题未完全解决
- **问题**: 
  - ✅ 转义标识符已修复：`\fifo_instance.fifomem.waddr[3]` → `fifo_instance_fifomem_waddr_3`
  - ⚠️ 隔离单元（ISOLANDX1_RVT, ISOLORX1_RVT）替换后仍有语法错误
- **建议**: 重新综合，禁用隔离单元生成

### 2. jpeg
- **状态**: ⚠️ 转义标识符已修复，但仍有语法错误
- **问题**: `syntax error in gate pin-net mapping`
- **已修复**: ✅ 转义标识符
- **需要**: 检查具体语法错误位置

### 3. ethmac
- **状态**: ⚠️ 转义标识符已修复，但仍有语法错误
- **问题**: `missing ; in instance declaration`
- **已修复**: ✅ 转义标识符
- **需要**: 检查实例声明格式

## 修复工具

### fix_ports.py
- 修复简单转义标识符：`\name[index]` → `name_index`
- 修复复杂转义标识符：`\name.subname[index]` → `name_subname_index`

### fix_isolation_cells.py
- 替换 ISOLANDX1_RVT → INVX0_RVT + AND2X1_RVT
- 替换 ISOLORX1_RVT → OR2X1_RVT

## 当前可用 Benchmark

**5个 benchmark 可以正常运行 OpenTimer：**
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
1. **选项1**: 重新综合，在 Yosys 脚本中添加选项禁用隔离单元
2. **选项2**: 检查 OpenTimer 源代码，了解具体语法要求
3. **选项3**: 使用当前 5 个可用的 benchmark 继续研究
