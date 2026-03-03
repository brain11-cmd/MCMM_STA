# Quick clock period optimization - tests key periods only
param(
    [string]$OpenTimerPath = "D:\opentimer\OpenTimer\bin\ot-shell",
    [string]$LibPath = "D:\bishe_database\BUFLIB\lib_rvt\saed32rvt_tt1p05v25c.lib",
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists"
)

$benchmarks = @("gcd", "uart", "spi", "fifo", "aes", "jpeg", "ethmac", "dynamic_node")
$testPeriods = @(1.0, 0.5, 0.3, 0.2, 0.15, 0.1, 0.08)

Write-Host "============================================"
Write-Host "Quick Clock Period Optimization"
Write-Host "============================================"
Write-Host "Testing periods: $($testPeriods -join ', ') ns"
Write-Host ""

$results = @()

foreach ($bm in $benchmarks) {
    $netlistFile = Join-Path $NetlistDir "$bm\${bm}_netlist.v"
    $sdcFile = Join-Path $NetlistDir "$bm\$bm.sdc"
    
    if (-not (Test-Path $netlistFile) -or -not (Test-Path $sdcFile)) {
        Write-Host "[$bm] Files not found, skipping"
        continue
    }
    
    Write-Host "[$bm] Testing..." -NoNewline
    
    # Read original SDC
    $sdcContent = Get-Content $sdcFile -Raw
    if ($sdcContent -notmatch 'create_clock.*-period\s+([\d.]+)') {
        Write-Host " Cannot parse SDC"
        continue
    }
    
    $originalPeriod = [double]$matches[1]
    $optimalPeriod = $originalPeriod
    $optimalWNS = 0
    $optimalFreq = 0
    
    # Only test periods smaller than original (better performance)
    $testPeriods = $testPeriods | Where-Object { $_ -lt $originalPeriod }
    
    if ($testPeriods.Count -eq 0) {
        Write-Host " Already optimized or no smaller periods to test"
        continue
    }
    
    foreach ($testPeriod in $testPeriods) {
        # Create temp SDC
        $tempSDC = Join-Path $NetlistDir "$bm\temp_${testPeriod}ns.sdc"
        $newSDC = $sdcContent -replace '(create_clock.*-period\s+)[\d.]+', "`${1}$testPeriod"
        Set-Content -Path $tempSDC -Value $newSDC -Encoding UTF8
        
        # Create test script
        $testScript = Join-Path $NetlistDir "$bm\temp_test.tcl"
        $wslNetlist = "/mnt/d/bishe_database/benchmark/netlists/$bm/${bm}_netlist.v"
        $wslSDC = "/mnt/d/bishe_database/benchmark/netlists/$bm/temp_${testPeriod}ns.sdc"
        
        $scriptContent = "read_celllib /mnt/d/bishe_database/BUFLIB/lib_rvt/saed32rvt_tt1p05v25c.lib`n"
        $scriptContent += "read_verilog $wslNetlist`n"
        $scriptContent += "read_sdc $wslSDC`n"
        $scriptContent += "update_timing`n"
        $scriptContent += "report_wns`n"
        $scriptContent += "report_tns`n"
        
        [System.IO.File]::WriteAllText($testScript, $scriptContent, [System.Text.UTF8Encoding]::new($false))
        
        # Run OpenTimer
        $wslScript = $testScript -replace 'D:\\', '/mnt/d/' -replace '\\', '/'
        $output = wsl bash -c "cd /mnt/d/opentimer/OpenTimer && ./bin/ot-shell < $wslScript" 2>&1
        
        # Parse results
        $numericValues = $output | Where-Object { $_ -match '^-?[\d.]+$' -and $_ -notmatch '^[0-9]{5,}' } | ForEach-Object { [double]$_ }
        
        if ($numericValues.Count -ge 2) {
            $wns = $numericValues[0]
            $tns = $numericValues[1]
            
            if ($wns -ge 0.01 -and $tns -eq 0) {
                $optimalPeriod = $testPeriod
                $optimalWNS = $wns
                $optimalFreq = [math]::Round(1000.0 / $testPeriod, 2)
            } else {
                break
            }
        }
        
        # Cleanup
        Remove-Item -Path $tempSDC -ErrorAction SilentlyContinue
        Remove-Item -Path $testScript -ErrorAction SilentlyContinue
    }
    
    if ($optimalPeriod -ne $originalPeriod) {
        # Update SDC
        $newSDC = $sdcContent -replace '(create_clock.*-period\s+)[\d.]+', "`${1}$optimalPeriod"
        $newSDC = $newSDC -replace '(# Clock period:)[^\n]*', "`${1} ${optimalPeriod}ns (Optimized from ${originalPeriod}ns, ${optimalFreq} MHz)"
        Set-Content -Path $sdcFile -Value $newSDC -Encoding UTF8
        
        $improvement = [math]::Round($originalPeriod / $optimalPeriod, 1)
        Write-Host " ${optimalPeriod}ns ($optimalFreq MHz, ${improvement}x, WNS: $optimalWNS ns)"
        
        $results += [PSCustomObject]@{
            Benchmark = $bm
            Original = "${originalPeriod}ns"
            Optimal = "${optimalPeriod}ns"
            Frequency = "${optimalFreq} MHz"
            Improvement = "${improvement}x"
            WNS = "$optimalWNS ns"
        }
    } else {
        Write-Host " No improvement found"
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "Summary"
Write-Host "============================================"
if ($results.Count -gt 0) {
    $results | Format-Table -AutoSize
    $resultsFile = Join-Path $NetlistDir "optimization_results.csv"
    $results | Export-Csv -Path $resultsFile -NoTypeInformation
    Write-Host "Results saved to: $resultsFile"
} else {
    Write-Host "No optimizations found"
}

