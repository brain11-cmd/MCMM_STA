# Push project to GitHub
# Usage: .\push_to_github.ps1 -GitHubUser "your_username" -GitHubEmail "your_email@example.com"

param(
    [string]$GitHubUser = "brain11-cmd",
    [string]$GitHubEmail = ""
)

Write-Host "============================================"
Write-Host "Pushing to GitHub: MCMM_STA"
Write-Host "============================================"
Write-Host ""

# Configure git user (if not set)
$currentUser = git config user.name
$currentEmail = git config user.email

if (-not $currentUser) {
    if ($GitHubEmail) {
        git config user.email $GitHubEmail
    } else {
        $GitHubEmail = Read-Host "Enter your GitHub email"
        git config user.email $GitHubEmail
    }
    git config user.name $GitHubUser
    Write-Host "✓ Git user configured: $GitHubUser <$GitHubEmail>"
} else {
    Write-Host "Git user already configured: $currentUser <$currentEmail>"
}

# Check remote
$remote = git remote get-url origin 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Adding remote repository..."
    git remote add origin https://github.com/brain11-cmd/MCMM_STA.git
} else {
    Write-Host "Remote already configured: $remote"
}

# Check if there are changes to commit
$status = git status --short
if ($status) {
    Write-Host ""
    Write-Host "Staging files..."
    git add .
    
    Write-Host "Committing changes..."
    git commit -m "Initial commit: Multi-corner STA project for GNN-based timing prediction

- Added benchmark designs (RTL sources and synthesized netlists)
- Added SAED32 standard cell libraries (27 PVT corners for RVT)
- Added synthesis and optimization scripts
- Added OpenTimer modifications (arc.hpp for delay access)
- 5 working benchmarks: gcd, uart, spi, aes, dynamic_node
- Optimized clock periods for all working benchmarks"
    
    Write-Host "✓ Changes committed"
} else {
    Write-Host "No changes to commit"
}

# Push to GitHub
Write-Host ""
Write-Host "Pushing to GitHub..."
Write-Host "Repository: https://github.com/brain11-cmd/MCMM_STA.git"
Write-Host ""

# Set default branch to main
git branch -M main 2>&1 | Out-Null

# Push
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================"
    Write-Host "✓ Successfully pushed to GitHub!"
    Write-Host "============================================"
    Write-Host "Repository: https://github.com/brain11-cmd/MCMM_STA"
} else {
    Write-Host ""
    Write-Host "============================================"
    Write-Host "Push failed. Common issues:"
    Write-Host "============================================"
    Write-Host "1. Authentication required - use GitHub CLI or Personal Access Token"
    Write-Host "2. Repository might not be empty - try: git pull --allow-unrelated-histories"
    Write-Host "3. Check your internet connection"
    Write-Host ""
    Write-Host "To authenticate, you can:"
    Write-Host "  - Use GitHub CLI: gh auth login"
    Write-Host "  - Use Personal Access Token in URL:"
    Write-Host "    git remote set-url origin https://TOKEN@github.com/brain11-cmd/MCMM_STA.git"
}























