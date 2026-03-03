# 验证从 endpoint slack 计算的 WNS/TNS 与 report_wns/report_tns 是否一致
param(
    [string]$Benchmark = "gcd",
    [string]$Corner = "saed32rvt_tt1p05v25c",
    [string]$LibPath = "D:\bishe_database\BUFLIB\lib_rvt\${Corner}.lib",
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists"
)

$netlistFile = Join-Path $NetlistDir "$Benchmark\${Benchmark}_netlist.v"
$sdcFile = Join-Path $NetlistDir "$Benchmark\$Benchmark.sdc"

if (-not (Test-Path $LibPath)) {
    Write-Host "库文件不存在: $LibPath" -ForegroundColor Red
    exit 1
}

# 路径转换
$libPathWSL = $LibPath -replace '\\', '/' -replace '^D:', '/mnt/d'
$netlistPathWSL = $netlistFile -replace '\\', '/' -replace '^D:', '/mnt/d'
$sdcPathWSL = $sdcFile -replace '\\', '/' -replace '^D:', '/mnt/d'

# 创建 TCL 脚本 - 先获取 report_wns/report_tns
$wslTcl1 = "/tmp/ot_${Benchmark}_${Corner}_report.tcl"
$tclContent1 = @"
read_celllib $libPathWSL
read_verilog $netlistPathWSL
read_sdc $sdcPathWSL
update_timing
report_wns
report_tns
"@

$wslCmd1 = "cat > $wslTcl1 << 'EOF'
$tclContent1
EOF
"
wsl bash -c $wslCmd1 | Out-Null

Write-Host "运行 OpenTimer 获取 report_wns/report_tns..." -ForegroundColor Cyan
$output1 = wsl bash -c "cd /mnt/d/opentimer/OpenTimer && timeout 300 ./bin/ot-shell < $wslTcl1" 2>&1

# 解析 WNS/TNS
$wnsReport = $null
$tnsReport = $null
$numericValues = @()
foreach ($line in ($output1 -split "`n")) {
    $trimmed = $line.Trim()
    if ($trimmed -match '^-?\d+(\.\d+)?$') {
        $numericValues += [double]$trimmed
    }
}
if ($numericValues.Count -ge 1) {
    $wnsReport = $numericValues[0]
    $tnsReport = if ($numericValues.Count -ge 2) { $numericValues[1] } else { 0 }
}

# 导出 slack 数据
$wslTcl2 = "/tmp/ot_${Benchmark}_${Corner}_slack.tcl"
$slackFile = "/tmp/${Benchmark}_${Corner}_slack.txt"
$tclContent2 = @"
read_celllib $libPathWSL
read_verilog $netlistPathWSL
read_sdc $sdcPathWSL
update_timing
dump_slack -o $slackFile
"@

$wslCmd2 = "cat > $wslTcl2 << 'EOF'
$tclContent2
EOF
"
wsl bash -c $wslCmd2 | Out-Null

Write-Host "运行 OpenTimer 导出 slack 数据..." -ForegroundColor Cyan
wsl bash -c "cd /mnt/d/opentimer/OpenTimer && timeout 300 ./bin/ot-shell < $wslTcl2" 2>&1 | Out-Null

# 解析 slack 文件，计算 WNS/TNS
Write-Host "解析 slack 文件并计算 WNS/TNS..." -ForegroundColor Cyan
$slackContent = wsl bash -c "cat $slackFile"

$allSlacks = @()
$lateSlacks = @()
$inDataSection = $false

foreach ($line in ($slackContent -split "`n")) {
    $trimmed = $line.Trim()
    
    if ($trimmed -match '^Slack \[pins:') {
        $inDataSection = $false
        continue
    }
    
    if ($trimmed -match '^-+$') {
        $inDataSection = $true
        continue
    }
    
    if ($inDataSection -and $trimmed -match '^\s*([\d\.-]+|n/a)\s+([\d\.-]+|n/a)\s+([\d\.-]+|n/a)\s+([\d\.-]+|n/a)\s+(\S+)') {
        # 解析 E/R, E/F, L/R, L/F
        $er = if ($matches[1] -ne 'n/a') { [double]$matches[1] } else { $null }
        $ef = if ($matches[2] -ne 'n/a') { [double]$matches[2] } else { $null }
        $lr = if ($matches[3] -ne 'n/a') { [double]$matches[3] } else { $null }
        $lf = if ($matches[4] -ne 'n/a') { [double]$matches[4] } else { $null }
        
        # 收集所有有效的 slack 值
        # WNS 通常关注 setup time，即 Late (L/R, L/F)
        # 但为了完整性，我们也收集 Early
        if ($null -ne $er) { $allSlacks += $er }
        if ($null -ne $ef) { $allSlacks += $ef }
        if ($null -ne $lr) { $allSlacks += $lr }
        if ($null -ne $lf) { $allSlacks += $lf }
        
        # 单独收集 Late slack（setup time 检查）
        if ($null -ne $lr) { $lateSlacks += $lr }
        if ($null -ne $lf) { $lateSlacks += $lf }
    }
}

# 计算 WNS = min(slack)
# WNS 通常关注 setup time，即 Late slack 的最小值
$wnsFromAll = if ($allSlacks.Count -gt 0) { ($allSlacks | Measure-Object -Minimum).Minimum } else { $null }
$wnsFromLate = if ($lateSlacks.Count -gt 0) { ($lateSlacks | Measure-Object -Minimum).Minimum } else { $null }
$wnsCalculated = $wnsFromLate  # 使用 Late slack

# 计算 TNS = sum(min(0, slack))，即所有负 slack 的和
$negativeSlacks = $allSlacks | Where-Object { $_ -lt 0 }
$tnsCalculated = if ($negativeSlacks.Count -gt 0) { ($negativeSlacks | Measure-Object -Sum).Sum } else { 0 }

# 输出对比结果
Write-Host "`n========================================" -ForegroundColor Yellow
Write-Host "WNS/TNS 计算结果对比" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "Corner: $Corner" -ForegroundColor Cyan
Write-Host "Benchmark: $Benchmark" -ForegroundColor Cyan
Write-Host ""
Write-Host "方法 1: report_wns / report_tns (OpenTimer 直接报告)" -ForegroundColor Green
Write-Host "  WNS = $wnsReport" -ForegroundColor White
Write-Host "  TNS = $tnsReport" -ForegroundColor White
Write-Host ""
Write-Host "方法 2: 从 endpoint slack 计算" -ForegroundColor Green
Write-Host "  WNS = min(Late slack) = $wnsCalculated" -ForegroundColor White
Write-Host "  WNS (所有 slack) = $wnsFromAll" -ForegroundColor Gray
Write-Host "  TNS = sum(min(0, slack)) = $tnsCalculated" -ForegroundColor White
Write-Host ""
Write-Host "统计信息:" -ForegroundColor Cyan
Write-Host "  总 slack 值数量: $($allSlacks.Count)" -ForegroundColor White
Write-Host "  Late slack 数量: $($lateSlacks.Count)" -ForegroundColor White
Write-Host "  负 slack 数量: $($negativeSlacks.Count)" -ForegroundColor White
Write-Host ""

# 验证一致性
$wnsMatch = if ($wnsReport -ne $null -and $wnsCalculated -ne $null) {
    [math]::Abs($wnsReport - $wnsCalculated) -lt 0.0001
} else { $false }

$tnsMatch = if ($tnsReport -ne $null -and $tnsCalculated -ne $null) {
    [math]::Abs($tnsReport - $tnsCalculated) -lt 0.0001
} else { $false }

if ($wnsMatch -and $tnsMatch) {
    Write-Host "✅ 结果一致！" -ForegroundColor Green
} else {
    Write-Host "⚠️ 结果不一致，差异:" -ForegroundColor Yellow
    if (-not $wnsMatch) {
        $diff = [math]::Abs($wnsReport - $wnsCalculated)
        Write-Host "  WNS 差异: $diff" -ForegroundColor Yellow
    }
    if (-not $tnsMatch) {
        $diff = [math]::Abs($tnsReport - $tnsCalculated)
        Write-Host "  TNS 差异: $diff" -ForegroundColor Yellow
    }
}

# 清理
wsl bash -c "rm -f $wslTcl1 $wslTcl2 $slackFile" | Out-Null

