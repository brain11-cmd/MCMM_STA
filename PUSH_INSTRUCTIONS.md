# 推送到 GitHub 的步骤

## 当前状态

✅ Git 仓库已初始化
✅ 所有文件已添加到 git
✅ 已创建初始提交
✅ 远程仓库已配置: https://github.com/brain11-cmd/MCMM_STA.git

## 推送步骤

### 方法 1: 使用 GitHub CLI（推荐）

```powershell
cd D:\bishe_database

# 如果还没安装 GitHub CLI，先安装
# winget install GitHub.cli

# 登录 GitHub
gh auth login

# 推送
git push -u origin main
```

### 方法 2: 使用 Personal Access Token

1. 在 GitHub 创建 Personal Access Token:
   - 访问: https://github.com/settings/tokens
   - 点击 "Generate new token (classic)"
   - 选择权限: `repo` (完整仓库访问权限)
   - 复制生成的 token

2. 使用 token 推送:
```powershell
cd D:\bishe_database

# 使用 token 设置远程 URL
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

## 如果仓库不为空

如果 GitHub 仓库已经有内容（如 README），需要先拉取：

```powershell
git pull origin main --allow-unrelated-histories
# 解决可能的冲突
git push -u origin main
```

## 检查推送状态

```powershell
git status
git log --oneline -5
```

## 注意事项

1. **库文件大小**: BUFLIB 文件夹可能很大，如果推送失败，考虑：
   - 使用 Git LFS: `git lfs track "*.lib"`
   - 或者排除库文件（编辑 .gitignore）

2. **OpenTimer**: 当前只包含修改的文件，完整的 OpenTimer 可以作为子模块添加

3. **认证**: 确保你有推送权限到 brain11-cmd/MCMM_STA 仓库

## 推送成功后

访问 https://github.com/brain11-cmd/MCMM_STA 查看你的代码！

