# Test chameleon with different library corners
param(
    [string]$Benchmark = "chameleon",
    [string]$LibDir = "D:\bishe_database\BUFLIB\lib_rvt",
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists"
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Testing $Benchmark with Different Libraries" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Select representative libraries to test
$testLibs = @(
    @{Name="tt1p05v25c"; File="saed32rvt_tt1p05v25c.lib"; Desc="Typical, 1.05V, 25°C (current)"},
    @{Name="ff1p16v25c"; File="saed32rvt_ff1p16v25c.lib"; Desc="Fast, 1.16V, 25°C"},
    @{Name="ss0p7v125c"; File="saed32rvt_ss0p7v125c.lib"; Desc="Slow, 0.7V, 125°C"},
    @{Name="tt0p85v25c"; File="saed32rvt_tt0p85v25c.lib"; Desc="Typical, 0.85V, 25°C"},
    @{Name="ff0p95v25c"; File="saed32rvt_ff0p95v25c.lib"; Desc="Fast, 0.95V, 25°C"}
)

$netlistFile = Join-Path $NetlistDir "$Benchmark\${Benchmark}_netlist.v"
$sdcFile = Join-Path $NetlistDir "$Benchmark\$Benchmark.sdc"

if (-not (Test-Path $netlistFile)) {
    Write-Host "ERROR: Netlist not found: $netlistFile" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $sdcFile)) {
    Write-Host "ERROR: SDC not found: $sdcFile" -ForegroundColor Red
    exit 1
}

$results = @()

foreach ($lib in $testLibs) {
    $libPath = Join-Path $LibDir $lib.File
    if (-not (Test-Path $libPath)) {
        Write-Host "WARNING: Library not found: $libPath" -ForegroundColor Yellow
        continue
    }
    
    Write-Host "Testing: $($lib.Desc)" -ForegroundColor Yellow
    Write-Host "  Library: $($lib.File)" -ForegroundColor Gray
    
    # Path conversion for WSL
    $libPathWSL = $libPath -replace '\\', '/' -replace '^D:', '/mnt/d'
    $netlistPathWSL = $netlistFile -replace '\\', '/' -replace '^D:', '/mnt/d'
    $sdcPathWSL = $sdcFile -replace '\\', '/' -replace '^D:', '/mnt/d'
    
    # Create TCL script
    $wslTcl = "/tmp/ot_test_${Benchmark}_$($lib.Name).tcl"
    $tclContent = @"
read_celllib $libPathWSL
read_verilog $netlistPathWSL
read_sdc $sdcPathWSL
update_timing
report_wns
report_tns
EOF
"@
    
    $wslCmd = "cat > $wslTcl << 'EOF'
$tclContent
EOF
"
    
    wsl bash -c $wslCmd | Out-Null
    
    # Run OpenTimer
    $output = wsl bash -c "cd /mnt/d/opentimer/OpenTimer && timeout 60 ./bin/ot-shell < $wslTcl" 2>&1
    
    # Parse WNS and TNS
    $wns = $null
    $tns = $null
    
    foreach ($line in ($output -split "`n")) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^-?\d+\.?\d*$' -and $trimmed -notmatch '^[0-9]+$') {
            if ($null -eq $wns) {
                $wns = [double]$trimmed
            } elseif ($null -eq $tns) {
                $tns = [double]$trimmed
                break
            }
        }
    }
    
    if ($null -ne $wns -and $null -ne $tns) {
        $results += [PSCustomObject]@{
            Library = $lib.Name
            Description = $lib.Desc
            WNS = $wns
            TNS = $tns
        }
        Write-Host "  WNS: $wns ns" -ForegroundColor $(if ($wns -ge 0) { "Green" } else { "Red" })
        Write-Host "  TNS: $tns ns" -ForegroundColor $(if ($tns -ge 0) { "Green" } else { "Red" })
    } else {
        Write-Host "  ERROR: Failed to parse results" -ForegroundColor Red
    }
    Write-Host ""
}

# Summary
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if ($results.Count -gt 0) {
    $results | Format-Table -AutoSize
    
    Write-Host "`nObservations:" -ForegroundColor Yellow
    $bestWNS = ($results | Sort-Object WNS -Descending)[0]
    $worstWNS = ($results | Sort-Object WNS)[0]
    Write-Host "  Best WNS: $($bestWNS.Library) ($($bestWNS.WNS) ns)" -ForegroundColor Green
    Write-Host "  Worst WNS: $($worstWNS.Library) ($($worstWNS.WNS) ns)" -ForegroundColor Red
    Write-Host "  WNS Range: $($worstWNS.WNS) to $($bestWNS.WNS) ns ($([math]::Round($bestWNS.WNS - $worstWNS.WNS, 3)) ns difference)" -ForegroundColor Cyan
}


