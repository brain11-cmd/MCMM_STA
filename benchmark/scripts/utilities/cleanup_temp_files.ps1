# Cleanup temporary and test scripts
$filesToDelete = @(
    "test_chameleon_multicorner.ps1",
    "download_chameleon_rtl.ps1",
    "resynth_chameleon_real_rtl.ps1",
    "test_ethmac_simple.ps1",
    "test_fixed_benchmarks.ps1",
    "test_riscv32i_timing.ps1",
    "run_riscv32i_background.ps1",
    "run_riscv32i_timing.ps1",
    "check_timing_status.ps1",
    "fix_tns_parsing.ps1",
    "OT_RUN_LOG.md",
    "BENCHMARK_STATUS.md"
)

Write-Host "`n=== 清理临时文件 ===" -ForegroundColor Cyan
Write-Host ""

$deleted = 0
$notFound = 0

foreach ($file in $filesToDelete) {
    $filePath = Join-Path $PSScriptRoot $file
    if (Test-Path $filePath) {
        Remove-Item $filePath -Force
        Write-Host "✅ 已删除: $file" -ForegroundColor Green
        $deleted++
    } else {
        Write-Host "⚠️  未找到: $file" -ForegroundColor Gray
        $notFound++
    }
}

Write-Host ""
Write-Host "删除完成: $deleted 个文件" -ForegroundColor Cyan
if ($notFound -gt 0) {
    Write-Host "未找到: $notFound 个文件" -ForegroundColor Gray
}


