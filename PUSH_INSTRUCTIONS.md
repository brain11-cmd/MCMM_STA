# 推送到 GitHub 的步骤

## ✅ 当前状态

**所有三个文件夹已包含在仓库中：**
- ✅ `benchmark/` - 基准测试设计和脚本
- ✅ `BUFLIB/` - SAED32 标准单元库
- ✅ `opentimer/OpenTimer/` - OpenTimer 源代码（已修改）

**Git 状态：**
- ✅ 仓库已初始化
- ✅ 所有文件已添加（1107+ 个文件）
- ✅ 已创建 3 个提交
- ✅ 远程仓库已配置: https://github.com/brain11-cmd/MCMM_STA.git

## 推送步骤

### 方法 1: 使用 GitHub CLI（推荐）

```powershell
cd D:\bishe_database

# 如果还没安装 GitHub CLI，先安装
winget install GitHub.cli

# 登录 GitHub
gh auth login

# 推送
git push -u origin main
```

### 方法 2: 使用 Personal Access Token

1. **创建 Token**:
   - 访问: https://github.com/settings/tokens
   - 点击 "Generate new token (classic)"
   - 选择权限: `repo` (完整仓库访问权限)
   - 复制生成的 token

2. **使用 token 推送**:
```powershell
cd D:\bishe_database

# 使用 token 设置远程 URL（替换 YOUR_TOKEN）
git remote set-url origin https://YOUR_TOKEN@github.com/brain11-cmd/MCMM_STA.git

# 推送
git push -u origin main
```

### 方法 3: 使用 SSH（如果已配置 SSH key）

```powershell
cd D:\bishe_database

# 切换到 SSH URL
git remote set-url origin git@github.com:brain11-cmd/MCMM_STA.git

# 推送
git push -u origin main
```

### 方法 4: 使用自动化脚本

```powershell
cd D:\bishe_database
.\push_to_github.ps1 -GitHubEmail "your_email@example.com"
```

## 如果仓库不为空

如果 GitHub 仓库已经有内容（如 README），需要先拉取：

```powershell
git pull origin main --allow-unrelated-histories
# 解决可能的冲突（如果有）
git push -u origin main
```

## 检查推送状态

```powershell
# 查看状态
git status

# 查看提交历史
git log --oneline -5

# 查看远程仓库
git remote -v
```

## 注意事项

1. **库文件大小**: BUFLIB 文件夹可能很大（几 GB），如果推送失败：
   - 考虑使用 Git LFS: `git lfs track "*.lib"`
   - 或者排除库文件（编辑 .gitignore，取消注释 `BUFLIB/lib_*/*.lib`）

2. **OpenTimer**: 已包含源代码，但排除了 build/ 和 bin/ 目录（需要编译）

3. **认证**: 确保你有推送权限到 `brain11-cmd/MCMM_STA` 仓库

4. **文件数量**: 仓库包含 1100+ 个文件，首次推送可能需要一些时间

## 推送成功后

访问 https://github.com/brain11-cmd/MCMM_STA 查看你的代码！

## 仓库结构

```
MCMM_STA/
├── benchmark/          # 基准测试设计
│   ├── rtl_src/       # RTL 源代码
│   ├── netlists/      # 综合后的门级网表
│   └── scripts/      # 综合和优化脚本
├── BUFLIB/            # SAED32 标准单元库
│   ├── lib_rvt/       # RVT 库（27 个 PVT corners）
│   ├── lib_lvt/       # LVT 库
│   └── lib_hvt/       # HVT 库
└── opentimer/         # OpenTimer 时序分析工具
    └── OpenTimer/     # OpenTimer 源代码（已修改 arc.hpp）
```
