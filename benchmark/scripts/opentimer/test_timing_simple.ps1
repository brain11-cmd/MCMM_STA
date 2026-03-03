# Simple timing propagation test
param(
    [string]$Benchmark = "gcd",
    [string]$Corner = "tt0p85v25c",
    [string]$LibPath = "D:\bishe_database\BUFLIB\lib_rvt",
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists"
)

Write-Host "============================================"
Write-Host "Testing Timing Propagation: $Benchmark"
Write-Host "============================================"
Write-Host ""

# Paths
$libFile = Join-Path $LibPath "saed32rvt_${Corner}.lib"
$netlistFile = Join-Path $NetlistDir "$Benchmark\${Benchmark}_netlist.v"
$sdcFile = Join-Path $NetlistDir "$Benchmark\$Benchmark.sdc"

# Convert paths for WSL
$libPathWSL = $libFile -replace '\\', '/' -replace '^D:', '/mnt/d'
$netlistPathWSL = $netlistFile -replace '\\', '/' -replace '^D:', '/mnt/d'
$sdcPathWSL = $sdcFile -replace '\\', '/' -replace '^D:', '/mnt/d'

# Create simple TCL script
$wslTcl = "/tmp/ot_simple_${Benchmark}.tcl"
$tclContent = @"
read_celllib $libPathWSL
read_verilog $netlistPathWSL
read_sdc $sdcPathWSL
update_timing
report_wns
report_tns
report_fep
"@

$wslCmd = "cat > $wslTcl << 'EOF'
$tclContent
EOF
"

wsl bash -c $wslCmd | Out-Null

Write-Host "Running OpenTimer..." -ForegroundColor Cyan
Write-Host ""

$output = wsl bash -c "cd /mnt/d/opentimer/OpenTimer && timeout 600 ./bin/ot-shell < $wslTcl 2>&1"

Write-Host "OpenTimer Output:" -ForegroundColor Cyan
Write-Host "--------------------------------------------"
$outputLines = $output -split "`n"
$foundWNS = $false
$foundTNS = $false
$foundFEP = $false
$errorCount = 0

foreach ($line in $outputLines) {
    $trimmed = $line.Trim()
    
    # Show all output
    Write-Host $trimmed
    
    # Check for WNS/TNS
    if ($trimmed -match '^-?\d+\.?\d*$' -and -not $foundWNS) {
        $foundWNS = $true
        Write-Host "  [WNS found: $trimmed]" -ForegroundColor Green
    } elseif ($trimmed -match '^-?\d+\.?\d*$' -and $foundWNS -and -not $foundTNS) {
        $foundTNS = $true
        Write-Host "  [TNS found: $trimmed]" -ForegroundColor Green
    }
    
    # Check for FEP
    if ($trimmed -match 'FEP|fep|endpoint') {
        $foundFEP = $true
    }
    
    # Check for errors
    if ($trimmed -match 'ERROR|FATAL|Error|error|failed|Failed') {
        $errorCount++
        Write-Host "  [ERROR: $trimmed]" -ForegroundColor Red
    }
}

Write-Host "--------------------------------------------"
Write-Host ""

# Summary
Write-Host "Summary:" -ForegroundColor Cyan
if ($foundWNS) {
    Write-Host "  ✅ WNS reported" -ForegroundColor Green
} else {
    Write-Host "  ❌ WNS not found" -ForegroundColor Red
}

if ($foundTNS) {
    Write-Host "  ✅ TNS reported" -ForegroundColor Green
} else {
    Write-Host "  ❌ TNS not found" -ForegroundColor Red
}

if ($foundFEP) {
    Write-Host "  ✅ FEP reported" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  FEP not found" -ForegroundColor Yellow
}

if ($errorCount -gt 0) {
    Write-Host "  ❌ Found $errorCount error(s)" -ForegroundColor Red
} else {
    Write-Host "  ✅ No errors found" -ForegroundColor Green
}

# Check if arrival values are all n/a
Write-Host ""
Write-Host "Checking arrival.txt..." -ForegroundColor Cyan
$arrivalFile = "D:\bishe_database\benchmark\test_output\gcd\anchor_corners\tt0p85v25c\arrival.txt"
if (Test-Path $arrivalFile) {
    $arrivalContent = Get-Content $arrivalFile
    $nACount = 0
    $validCount = 0
    
    foreach ($line in $arrivalContent) {
        if ($line -match '\bn/a\b') {
            $nACount++
        } elseif ($line -match '\d+\.\d+') {
            $validCount++
        }
    }
    
    Write-Host "  Total lines: $($arrivalContent.Count)"
    Write-Host "  Lines with 'n/a': $nACount"
    Write-Host "  Lines with valid values: $validCount"
    
    if ($validCount -eq 0) {
        Write-Host "  ❌ All arrival values are n/a - timing propagation failed!" -ForegroundColor Red
        Write-Host ""
        Write-Host "Possible causes:" -ForegroundColor Yellow
        Write-Host "  1. Clock constraint not matching port names"
        Write-Host "  2. No valid timing paths found"
        Write-Host "  3. SDC file issues"
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Cyan
        Write-Host "  1. Check SDC file: $sdcFile"
        Write-Host "  2. Verify clock port name matches netlist"
        Write-Host "  3. Check OpenTimer output for warnings"
    } else {
        Write-Host "  ✅ Found $validCount valid arrival values" -ForegroundColor Green
    }
}

# Cleanup
wsl bash -c "rm -f $wslTcl" | Out-Null

Write-Host ""
Write-Host "============================================"


