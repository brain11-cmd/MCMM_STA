# 脚本整理指南

## 📋 整理方案总结

### 🗑️ 删除的文件（2个）
1. `script_analysis.txt` - 临时分析输出
2. `analyze_script_generality.py` - 一次性分析工具（已完成分析）

### 📦 移动到 deprecated/ 的文件（4个）
1. `过滤arc_delay.py` - 旧版本，功能已被 `canonicalize_arc_delay_json.py` 替代
2. `过滤instanace脚本.py` - 旧版本，功能已被 `unified_filter_pipeline.py` 替代
3. `compare_backup_files.py` - 一次性分析工具
4. `check_backup_duplicates.py` - 一次性分析工具

### 📁 文件夹分类（45个活跃脚本）

- **core/** (4个) - 核心处理脚本
- **data_generation/** (5个) - 数据生成脚本
- **validation/** (7个) - 验证脚本
- **analysis/** (6个) - 分析脚本
- **utilities/** (5个) - 工具脚本
- **opentimer/** (7个) - OpenTimer 相关
- **optimization/** (5个) - 优化脚本
- **synthesis/** (3个) - 综合脚本
- **maintenance/** (3个) - 维护脚本
- **docs/** (6个) - 文档
- **config/** (2个) - 配置文件

## 🚀 执行步骤

### Step 1: 预览整理计划
```bash
cd D:\bishe_database\benchmark\scripts
python organize_scripts.py --preview
```

### Step 2: 执行整理（确认后）
```bash
python organize_scripts.py --yes
```

### Step 3: 验证结果
检查文件是否都移动到正确位置，脚本是否仍然可以正常工作。

## ⚠️ 注意事项

1. **备份**：执行前建议备份整个 scripts 文件夹
2. **路径更新**：整理后，如果有其他脚本引用这些文件，需要更新路径
3. **测试**：整理后测试核心脚本是否仍然可以正常工作

## 📝 整理后的文件结构

```
scripts/
├── core/                    # 核心处理
├── data_generation/         # 数据生成
├── validation/              # 验证
├── analysis/                # 分析
├── utilities/               # 工具
├── opentimer/              # OpenTimer
├── optimization/            # 优化
├── synthesis/              # 综合
├── maintenance/            # 维护
├── docs/                   # 文档
├── config/                 # 配置
├── deprecated/             # 已废弃
├── organize_scripts.py     # 整理脚本（保留）
└── README.md               # 说明文档（自动生成）
```

## ✅ 整理后的好处

1. **清晰的组织结构** - 按功能分类，易于查找
2. **减少混乱** - 删除临时文件，废弃脚本单独存放
3. **易于维护** - 相关脚本集中在一起
4. **更好的文档** - 文档集中管理






















