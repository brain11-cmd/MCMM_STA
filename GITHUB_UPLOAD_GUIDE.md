# GitHub 上传指南

## 项目结构

本项目包含三个核心文件夹：
1. **benchmark/** - 基准测试设计和脚本
2. **BUFLIB/** - SAED32 标准单元库（27 个 PVT corners）
3. **OpenTimer/** - 时序分析工具（需要单独处理）

## 上传步骤

### 方案 1: 完整上传（推荐用于私有仓库）

如果库文件不太大（< 100MB），可以直接上传：

```powershell
cd D:\bishe_database

# 1. 初始化 git（已完成）
git init

# 2. 添加所有文件
git add .

# 3. 提交
git commit -m "Initial commit: Multi-corner STA project with benchmarks and libraries"

# 4. 在 GitHub 创建新仓库后，添加远程并推送
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 方案 2: 排除大型库文件（推荐用于公开仓库）

如果库文件很大，可以排除它们，只上传网表和脚本：

```powershell
# 编辑 .gitignore，取消注释这一行：
# BUFLIB/lib_*/*.lib

# 然后添加和提交
git add .
git commit -m "Initial commit: Multi-corner STA project (libraries excluded)"
```

### 方案 3: 使用 Git LFS（大文件支持）

如果库文件很大但需要上传：

```powershell
# 安装 Git LFS
git lfs install

# 跟踪 .lib 文件
git lfs track "*.lib"

# 添加和提交
git add .gitattributes
git add .
git commit -m "Initial commit with Git LFS for library files"
```

## OpenTimer 处理

OpenTimer 是一个独立的 git 仓库，有两种处理方式：

### 方式 1: Git 子模块（推荐）

```powershell
# 在 bishe_database 目录下
git submodule add https://github.com/OpenTimer/OpenTimer.git opentimer/OpenTimer

# 或者使用本地路径（如果已修改）
git submodule add -f D:/opentimer/OpenTimer opentimer/OpenTimer
```

### 方式 2: 单独上传

将 OpenTimer 作为单独的仓库上传，然后在 README 中说明。

### 方式 3: 只上传修改的文件

只上传你修改的部分（如 `ot/timer/arc.hpp`），在 README 中说明如何获取完整的 OpenTimer。

## 快速上传命令

```powershell
cd D:\bishe_database

# 检查文件大小
Write-Host "Checking file sizes..."
$benchmarkSize = (Get-ChildItem -Path "benchmark" -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB
$buflibSize = (Get-ChildItem -Path "BUFLIB" -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1GB
Write-Host "Benchmark: $([math]::Round($benchmarkSize, 2)) MB"
Write-Host "BUFLIB: $([math]::Round($buflibSize, 2)) GB"

# 添加文件（排除大型库文件，如果需要）
# 编辑 .gitignore 取消注释: BUFLIB/lib_*/*.lib

git add .
git commit -m "Initial commit: Multi-corner STA project for GNN-based timing prediction"

# 创建 GitHub 仓库后执行：
# git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
# git push -u origin main
```

## 注意事项

1. **库文件大小**: BUFLIB 可能很大（几 GB），考虑使用 Git LFS 或排除它们
2. **OpenTimer**: 建议作为子模块添加，保持与上游同步
3. **敏感信息**: 检查是否有 API keys 或其他敏感信息
4. **许可证**: 确保遵守 OpenTimer 和 SAED32 库的许可证

## 推荐配置

对于毕业设计项目，建议：
- ✅ 上传所有 benchmark 网表和脚本
- ✅ 上传 RTL 源代码
- ⚠️ 库文件：如果 < 100MB 直接上传，否则使用 Git LFS 或排除
- ✅ OpenTimer：作为子模块或单独仓库

