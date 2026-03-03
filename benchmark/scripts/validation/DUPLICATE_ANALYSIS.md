# Validation 脚本重复分析

## 📋 脚本功能对比

### 1. **verify_arc_delay.py** ❌
- **功能**: 验证 arc_delay.json 是否还有重复边
- **检查项**: 重复的 (src, dst, edge_type)
- **状态**: ❌ 硬编码路径（gcd, tt0p85v25c）
- **参数化**: ❌ 无

### 2. **check_edge_id_alignment.py** ❌
- **功能**: 检查 arc_delay.json 的 edge_id 是否正确对齐
- **检查项**: 
  - 重复的 edge_id
  - 重复的 (src, dst, edge_type)
- **状态**: ❌ 硬编码路径（gcd, tt0p85v25c）
- **参数化**: ❌ 无

### 3. **verify_canonical_edge_id.py** ❌
- **功能**: 验证 graph_edges.csv 的 edge_id 是否连续
- **检查项**: edge_id 是否连续（0-N-1）
- **状态**: ❌ 硬编码路径（gcd）
- **参数化**: ❌ 无

### 4. **check_node_edge_alignment.py** ❌
- **功能**: 检查 node_static_train.csv 和 graph_edges.csv 的对齐关系
- **检查项**: 
  - 节点和边的 pin 对齐
  - 覆盖率检查
- **状态**: ❌ 硬编码路径（gcd）
- **参数化**: ❌ 无

### 5. **check_node_consistency.py** ⚠️
- **功能**: 检查节点一致性（跨文件）
- **检查项**: 
  - arc_delay.json 中的节点
  - arrival.txt 中的节点
  - graph.dot 中的节点
- **状态**: ⚠️ benchmark 已参数化，但 corner 硬编码（tt0p85v25c）
- **参数化**: 部分（需要添加 corner 参数）

### 6. **check_arc_arrival_correspondence.py** ✅
- **功能**: 检查 arrival.txt 和 arc_delay.json 的对应关系，分析重复边
- **检查项**: 
  - arrival.txt 和 arc_delay.json 的 pin 对应
  - arc_delay.txt 中的重复边分析
- **状态**: ✅ 完全参数化
- **参数化**: ✅ 使用 sys.argv

### 7. **validate_exported_data.py** ✅
- **功能**: 验证导出数据的一致性和正确性（综合验证）
- **检查项**: 
  - Edge 一致性（arcs vs DOT）
  - 覆盖率（dump_at pins vs node_static pins）
  - 唯一性（normalized pin_name）
- **状态**: ✅ 完全参数化
- **参数化**: ✅ 使用 argparse

## 🔍 重复功能分析

### 重复 1: Edge ID 检查
- **verify_canonical_edge_id.py** - 检查 graph_edges.csv 的 edge_id 连续性
- **check_edge_id_alignment.py** - 检查 arc_delay.json 的 edge_id 唯一性和对齐

**结论**: 
- 功能不同：一个检查 CSV，一个检查 JSON
- 但都检查 edge_id，可以合并为一个脚本

### 重复 2: 重复边检查
- **verify_arc_delay.py** - 检查 arc_delay.json 的重复边
- **check_edge_id_alignment.py** - 也检查重复的 (src, dst, edge_type)
- **check_arc_arrival_correspondence.py** - 也分析重复边

**结论**: 
- 功能重叠：都检查重复边
- **verify_arc_delay.py** 和 **check_edge_id_alignment.py** 功能几乎相同
- 可以合并或删除其中一个

### 重复 3: 对齐检查
- **check_node_edge_alignment.py** - 检查节点和边的对齐
- **check_node_consistency.py** - 也检查节点一致性
- **validate_exported_data.py** - 也检查覆盖率和对齐

**结论**: 
- 功能有重叠，但侧重点不同
- **check_node_edge_alignment.py** 专门检查 node_static 和 graph_edges
- **check_node_consistency.py** 检查跨文件一致性
- **validate_exported_data.py** 是综合验证

## 🗑️ 建议删除/合并

### 可以删除的脚本（功能重复）

1. **verify_arc_delay.py** ❌
   - 功能完全被 `check_edge_id_alignment.py` 覆盖
   - 且 `check_edge_id_alignment.py` 检查更全面（还检查 edge_id 唯一性）
   - **建议**: 删除或移动到 `deprecated/`

2. **verify_canonical_edge_id.py** ⚠️
   - 功能单一（只检查 edge_id 连续性）
   - 可以合并到 `check_edge_id_alignment.py` 中
   - **建议**: 合并功能后删除，或移动到 `deprecated/`

### 需要修复的脚本（硬编码）

3. **check_edge_id_alignment.py** ⚠️
   - 功能有用，但硬编码路径
   - **建议**: 修复为参数化

4. **check_node_edge_alignment.py** ⚠️
   - 功能有用，但硬编码路径
   - **建议**: 修复为参数化

5. **check_node_consistency.py** ⚠️
   - 功能有用，但 corner 硬编码
   - **建议**: 添加 corner 参数

## ✅ 保留的脚本（功能独特且已参数化）

1. **check_arc_arrival_correspondence.py** ✅
   - 功能独特：检查 arrival.txt 和 arc_delay.json 的对应关系
   - 已参数化

2. **validate_exported_data.py** ✅
   - 功能独特：综合验证（edge 一致性、覆盖率、唯一性）
   - 已参数化

## 📊 总结

- **总脚本数**: 7 个
- **建议删除**: 2 个（verify_arc_delay.py, verify_canonical_edge_id.py）
- **需要修复**: 3 个（check_edge_id_alignment.py, check_node_edge_alignment.py, check_node_consistency.py）
- **保留**: 2 个（check_arc_arrival_correspondence.py, validate_exported_data.py）

## 🔧 建议操作

1. **删除重复脚本**:
   - `verify_arc_delay.py` → 移动到 `deprecated/` 或删除
   - `verify_canonical_edge_id.py` → 合并功能到 `check_edge_id_alignment.py` 后删除

2. **修复硬编码脚本**:
   - 修复 `check_edge_id_alignment.py` 添加参数
   - 修复 `check_node_edge_alignment.py` 添加参数
   - 修复 `check_node_consistency.py` 添加 corner 参数

3. **合并功能**:
   - 将 `verify_canonical_edge_id.py` 的功能合并到 `check_edge_id_alignment.py`






















