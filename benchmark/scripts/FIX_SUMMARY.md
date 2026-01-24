# Benchmark 修复总结

## 修复状态

### ✅ 已修复并可以运行（5个）
1. **gcd** - 正常运行
2. **uart** - 正常运行  
3. **spi** - 正常运行
4. **aes** - 正常运行
5. **dynamic_node** - 正常运行

### ⚠️ 需要进一步修复（3个）

#### 1. fifo
- **问题**: 包含隔离单元（ISOLANDX1_RVT, ISOLORX1_RVT），OpenTimer 不支持
- **已尝试**: 
  - ✅ 修复转义标识符（`\fifo_instance.fifomem.waddr[3]` → `fifo_instance_fifomem_waddr_3`）
  - ⚠️ 替换隔离单元为等效逻辑（仍有语法错误）
- **建议**: 重新综合，禁用隔离单元

#### 2. jpeg  
- **问题**: `syntax error in gate pin-net mapping`
- **已尝试**: ✅ 修复转义标识符
- **需要**: 检查具体语法错误位置

#### 3. ethmac
- **问题**: `missing ; in instance declaration`
- **已尝试**: ✅ 修复转义标识符
- **需要**: 检查实例声明格式

## 修复脚本

### fix_ports.py
- 修复转义标识符：`\name[index]` → `name_index`
- 修复复杂转义标识符：`\name.subname[index]` → `name_subname_index`

### fix_isolation_cells.py
- 替换 ISOLANDX1_RVT 为 INVX0_RVT + AND2X1_RVT
- 替换 ISOLORX1_RVT 为 OR2X1_RVT

## 建议

对于 fifo, jpeg, ethmac，建议：
1. **重新综合**：修改 Yosys 脚本，禁用隔离单元
2. **或者**：检查 OpenTimer 是否支持这些单元的其他配置
3. **或者**：使用其他综合工具生成网表

当前 5 个可用的 benchmark 已经足够进行 GNN 数据提取和多 corner 分析。

