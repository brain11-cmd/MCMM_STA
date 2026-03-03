# Automatically optimize clock period for all benchmarks
param(
    [string]$OpenTimerPath = "D:\opentimer\OpenTimer\bin\ot-shell",
    [string]$LibPath = "D:\bishe_database\BUFLIB\lib_rvt\saed32rvt_tt1p05v25c.lib",
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists",
    [double]$StartPeriod = 1.0,
    [double]$MinPeriod = 0.05,
    [double]$Step = 0.05,
    [double]$TargetSlack = 0.01
)

$benchmarks = @("gcd", "uart", "spi", "fifo", "aes", "jpeg", "ethmac", "dynamic_node")

Write-Host "============================================"
Write-Host "Optimizing Clock Period for All Benchmarks"
Write-Host "============================================"
Write-Host ""

$results = @()

foreach ($bm in $benchmarks) {
    $netlistFile = Join-Path $NetlistDir "$bm\${bm}_netlist.v"
    $sdcFile = Join-Path $NetlistDir "$bm\$bm.sdc"
    
    if (-not (Test-Path $netlistFile)) {
        Write-Host "[$bm] Netlist not found, skipping"
        continue
    }
    
    if (-not (Test-Path $sdcFile)) {
        Write-Host "[$bm] SDC not found, skipping"
        continue
    }
    
    Write-Host "[$bm] Finding optimal clock period..." -NoNewline
    
    # Read original SDC
    $sdcContent = Get-Content $sdcFile -Raw
    if ($sdcContent -notmatch 'create_clock.*-period\s+([\d.]+)') {
        Write-Host " Cannot parse original SDC"
        continue
    }
    
    $originalPeriod = [double]$matches[1]
    $optimalPeriod = $originalPeriod
    $optimalWNS = 0
    $foundOptimal = $false
    
    # Linear search from StartPeriod down to MinPeriod
    $testPeriods = @()
    for ($p = $StartPeriod; $p -ge $MinPeriod; $p -= $Step) {
        $testPeriods += [math]::Round($p, 3)
    }
    
    foreach ($testPeriod in $testPeriods) {
        # Create temporary SDC (preserve clock name)
        $tempSDC = Join-Path $NetlistDir "$bm\temp_${testPeriod}ns.sdc"
        $newSDC = $sdcContent -replace '(create_clock.*-period\s+)[\d.]+', "`${1}$testPeriod"
        Set-Content -Path $tempSDC -Value $newSDC -Encoding UTF8
        
        # Create test script
        $testScript = Join-Path $NetlistDir "$bm\temp_test.tcl"
        $scriptContent = @"
read_celllib /mnt/d/bishe_database/BUFLIB/lib_rvt/saed32rvt_tt1p05v25c.lib
read_verilog /mnt/d/bishe_database/benchmark/netlists/$bm/${bm}_netlist.v
read_sdc /mnt/d/bishe_database/benchmark/netlists/$bm/temp_${testPeriod}ns.sdc
update_timing
report_wns
report_tns
"@
        [System.IO.File]::WriteAllText($testScript, $scriptContent, [System.Text.UTF8Encoding]::new($false))
        
        # Convert Windows path to WSL path
        $wslTestScript = $testScript -replace 'D:\\', '/mnt/d/' -replace '\\', '/'
        $wslTempSDC = $tempSDC -replace 'D:\\', '/mnt/d/' -replace '\\', '/'
        
        # Run OpenTimer
        $output = wsl bash -c "cd /mnt/d/opentimer/OpenTimer && ./bin/ot-shell < $wslTestScript" 2>&1
        
        # Parse WNS and TNS - look for numeric values on separate lines
        $numericLines = $output | Where-Object { $_ -match '^-?[\d.]+$' } | ForEach-Object { [double]$_ }
        
        if ($numericLines.Count -ge 2) {
            $wns = $numericLines[0]
            $tns = $numericLines[1]
            
            if ($wns -ge $TargetSlack -and $tns -eq 0) {
                # Timing passes, this is better
                $optimalPeriod = $testPeriod
                $optimalWNS = $wns
                $foundOptimal = $true
            } else {
                # Timing fails, stop searching
                break
            }
        } else {
            # Cannot parse output, try next period
            continue
        }
        
        # Cleanup
        Remove-Item -Path $tempSDC -ErrorAction SilentlyContinue
        Remove-Item -Path $testScript -ErrorAction SilentlyContinue
    }
    
    if ($foundOptimal) {
        # Update SDC with optimal period
        $optimalSDC = $sdcContent -replace 'create_clock.*-period\s+[\d.]+', "create_clock -period $optimalPeriod"
        $optimalSDC = $optimalSDC -replace '# Clock period:.*', "# Clock period: ${optimalPeriod}ns (Optimized from ${originalPeriod}ns)"
        Set-Content -Path $sdcFile -Value $optimalSDC -Encoding UTF8
        
        $freq = [math]::Round(1000.0 / $optimalPeriod, 2)
        $improvement = [math]::Round($originalPeriod / $optimalPeriod, 1)
        
        Write-Host " Optimal: ${optimalPeriod}ns ($freq MHz, ${improvement}x improvement, WNS: $optimalWNS ns)"
        
        $results += [PSCustomObject]@{
            Benchmark = $bm
            OriginalPeriod = $originalPeriod
            OptimalPeriod = $optimalPeriod
            Frequency = $freq
            Improvement = "${improvement}x"
            WNS = $optimalWNS
        }
    } else {
        Write-Host " Failed to find optimal period"
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "Optimization Summary"
Write-Host "============================================"
$results | Format-Table -AutoSize

# Save results
$resultsFile = Join-Path $NetlistDir "optimization_results.csv"
$results | Export-Csv -Path $resultsFile -NoTypeInformation
Write-Host "Results saved to: $resultsFile"

