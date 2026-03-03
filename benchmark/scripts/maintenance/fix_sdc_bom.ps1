# Fix BOM in all SDC files
param(
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists"
)

Write-Host "============================================"
Write-Host "Fixing BOM in SDC files"
Write-Host "============================================"
Write-Host ""

$sdcFiles = Get-ChildItem -Path $NetlistDir -Filter "*.sdc" -Recurse

$fixedCount = 0
foreach ($file in $sdcFiles) {
    try {
        $content = [System.IO.File]::ReadAllBytes($file.FullName)
        
        # Check for UTF-8 BOM (EF BB BF)
        if ($content.Length -ge 3 -and $content[0] -eq 0xEF -and $content[1] -eq 0xBB -and $content[2] -eq 0xBF) {
            # Remove BOM
            $newContent = $content[3..($content.Length-1)]
            [System.IO.File]::WriteAllBytes($file.FullName, $newContent)
            Write-Host "  [FIXED] $($file.FullName)" -ForegroundColor Green
            $fixedCount++
        } else {
            Write-Host "  [OK] $($file.FullName)" -ForegroundColor Gray
        }
    } catch {
        Write-Host "  [ERROR] $($file.FullName): $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "Fixed $fixedCount SDC file(s)"
Write-Host "============================================"


