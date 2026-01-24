# Setup GitHub repository for the project
# This script initializes git and prepares for GitHub upload

Write-Host "============================================"
Write-Host "Setting up GitHub Repository"
Write-Host "============================================"
Write-Host ""

$repoPath = "D:\bishe_database"

# Check if git is installed
try {
    $gitVersion = git --version 2>&1
    Write-Host "Git found: $gitVersion"
} catch {
    Write-Host "Error: Git is not installed or not in PATH"
    Write-Host "Please install Git for Windows: https://git-scm.com/download/win"
    exit 1
}

# Navigate to project root
Set-Location $repoPath

# Initialize git repository if not exists
if (-not (Test-Path ".git")) {
    Write-Host "Initializing git repository..."
    git init
    Write-Host "✓ Git repository initialized"
} else {
    Write-Host "Git repository already exists"
}

# Check .gitignore
if (-not (Test-Path ".gitignore")) {
    Write-Host "Creating .gitignore..."
    # .gitignore is already created
    Write-Host "✓ .gitignore created"
} else {
    Write-Host "✓ .gitignore exists"
}

# Add files
Write-Host ""
Write-Host "Adding files to git..."
git add .

# Check status
Write-Host ""
Write-Host "Git status:"
git status --short | Select-Object -First 20

Write-Host ""
Write-Host "============================================"
Write-Host "Next Steps:"
Write-Host "============================================"
Write-Host ""
Write-Host "1. Create a new repository on GitHub:"
Write-Host "   - Go to https://github.com/new"
Write-Host "   - Create a new repository (e.g., 'mcmm-sta-gnn')"
Write-Host "   - Do NOT initialize with README (we already have one)"
Write-Host ""
Write-Host "2. Commit and push:"
Write-Host "   git commit -m 'Initial commit: Multi-corner STA project'"
Write-Host "   git branch -M main"
Write-Host "   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git"
Write-Host "   git push -u origin main"
Write-Host ""
Write-Host "Note: OpenTimer is a separate repository."
Write-Host "      You may want to add it as a git submodule or copy it separately."
Write-Host "============================================"

