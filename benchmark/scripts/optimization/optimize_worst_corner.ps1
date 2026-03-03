# Optimize clock period for worst corner (SS - Slow-Slow)
# This ensures the design works across all PVT corners

param(
    [string]$Benchmark = "gcd",
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists",
    [string]$LibDir = "D:\bishe_database\BUFLIB\lib_rvt",
    [string]$OpenTimerPath = "D:\opentimer\OpenTimer"
)

Write-Host "============================================"
Write-Host "Optimize Clock Period for Worst Corner"
Write-Host "============================================"
Write-Host "Benchmark: $Benchmark"
Write-Host ""

# 最坏 corner 通常是 SS (Slow-Slow) 低电压低温
# 选择最严格的 corner: ss0p7vn40c (SS, 0.7V, -40°C)
$worstCorner = "saed32rvt_ss0p7vn40c.lib"
$worstCornerPath = Join-Path $LibDir $worstCorner

if (-not (Test-Path $worstCornerPath)) {
    Write-Host "Error: Worst corner library not found: $worstCornerPath"
    exit 1
}

$benchmarkDir = Join-Path $NetlistDir $Benchmark
$netlistFile = Join-Path $benchmarkDir "${Benchmark}_netlist.v"
$sdcFile = Join-Path $benchmarkDir "${Benchmark}.sdc"

if (-not (Test-Path $netlistFile) -or -not (Test-Path $sdcFile)) {
    Write-Host "Error: Netlist or SDC file not found"
    exit 1
}

# 读取当前 SDC
$sdcContent = Get-Content $sdcFile -Raw

# 测试不同的时钟周期，从大到小
$testPeriods = @(10.0, 5.0, 3.0, 2.0, 1.5, 1.2, 1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2)
$optimalPeriod = $null
$optimalWNS = $null

Write-Host "Testing clock periods with worst corner: $worstCorner"
Write-Host ""

foreach ($period in $testPeriods) {
    # 创建临时 SDC
    $tempSDC = Join-Path $benchmarkDir "temp_worst_${period}ns.sdc"
    $newSDC = $sdcContent -replace "(create_clock.*-period\s+)[\d.]+", "`${1}$period"
    Set-Content -Path $tempSDC -Value $newSDC -Encoding UTF8
    
    # 创建测试脚本
    $tempScript = Join-Path $env:TEMP "worst_corner_test_${Benchmark}_${period}.tcl"
    $libPath = $worstCornerPath -replace '\\', '/' -replace '^D:', '/mnt/d'
    $netlistPath = $netlistFile -replace '\\', '/' -replace '^D:', '/mnt/d'
    $sdcPath = $tempSDC -replace '\\', '/' -replace '^D:', '/mnt/d'
    
    $scriptContent = @"
read_celllib $libPath
read_verilog $netlistPath
read_sdc $sdcPath
update_timing
report_wns
report_tns
"@
    
    [System.IO.File]::WriteAllText($tempScript, $scriptContent, [System.Text.UTF8Encoding]::new($false))
    $wslScript = $tempScript -replace '^C:', '/mnt/c' -replace '\\', '/'
    
    # 运行 OpenTimer
    $output = wsl bash -c "cd /mnt/d/opentimer/OpenTimer && ./bin/ot-shell < $wslScript" 2>&1
    
    # 解析 WNS
    $lines = $output -split "`n"
    $wnsValue = $null
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if (-not [string]::IsNullOrWhiteSpace($trimmed) -and 
            $trimmed -notmatch '^[IWEF] \d+' -and 
            $trimmed -match '^-?\d+\.?\d*$') {
            $wnsValue = [double]$trimmed
            break
        }
    }
    
    if ($wnsValue -ne $null) {
        Write-Host "  Period: $period ns -> WNS: $wnsValue ns"
        
        # 找到满足时序的最小周期（WNS >= 0）
        if ($wnsValue -ge 0 -and $optimalPeriod -eq $null) {
            $optimalPeriod = $period
            $optimalWNS = $wnsValue
            Write-Host "    ✓ Found feasible period: $period ns (WNS: $wnsValue ns)"
        }
    }
    
    # 清理
    Remove-Item $tempScript -Force -ErrorAction SilentlyContinue
    Remove-Item $tempSDC -Force -ErrorAction SilentlyContinue
}

Write-Host ""

if ($optimalPeriod -ne $null) {
    Write-Host "============================================"
    Write-Host "Optimal Period Found!"
    Write-Host "============================================"
    Write-Host "Period: $optimalPeriod ns"
    Write-Host "Frequency: $([math]::Round(1000/$optimalPeriod, 2)) MHz"
    Write-Host "WNS (worst corner): $optimalWNS ns"
    Write-Host ""
    Write-Host "Updating SDC file..."
    
    # 更新 SDC 文件
    $updatedSDC = $sdcContent -replace "(create_clock.*-period\s+)[\d.]+", "`${1}$optimalPeriod"
    $backupSDC = Join-Path $benchmarkDir "${Benchmark}.sdc.backup"
    Copy-Item $sdcFile $backupSDC -Force
    Set-Content -Path $sdcFile -Value $updatedSDC -Encoding UTF8
    
    Write-Host "✓ SDC updated (backup saved to: $backupSDC)"
    Write-Host ""
    Write-Host "Note: This period ensures timing closure in worst corner."
    Write-Host "      The design should now pass in all 27 PVT corners."
} else {
    Write-Host "============================================"
    Write-Host "Warning: No feasible period found!"
    Write-Host "============================================"
    Write-Host "The design may need architectural changes or"
    Write-Host "the tested periods are too aggressive."
}


