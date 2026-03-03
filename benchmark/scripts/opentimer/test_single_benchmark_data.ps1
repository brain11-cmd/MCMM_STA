# Test script for single benchmark data export and validation
# This script exports data from OpenTimer and validates consistency
param(
    [string]$Benchmark = "gcd",  # Start with a small benchmark
    [string]$Corner = "tt0p85v25c",  # Use anchor A_typ for testing
    [string]$LibPath = "D:\bishe_database\BUFLIB\lib_rvt",
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists",
    [string]$OutputDir = "D:\bishe_database\benchmark\test_output",
    [string]$OpenTimerPath = "D:\opentimer\OpenTimer"
)

Write-Host "============================================"
Write-Host "Testing Benchmark: $Benchmark"
Write-Host "Corner: $Corner"
Write-Host "============================================"
Write-Host ""

# Create output directory
$benchmarkOutputDir = Join-Path $OutputDir $Benchmark
$cornerOutputDir = Join-Path $benchmarkOutputDir "anchor_corners\$Corner"
New-Item -ItemType Directory -Force -Path $cornerOutputDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $benchmarkOutputDir "static") | Out-Null

# Paths
$libFile = Join-Path $LibPath "saed32rvt_${Corner}.lib"
$netlistFile = Join-Path $NetlistDir "$Benchmark\${Benchmark}_netlist.v"
$sdcFile = Join-Path $NetlistDir "$Benchmark\$Benchmark.sdc"

# Check files
if (-not (Test-Path $libFile)) {
    Write-Host "❌ Library file not found: $libFile" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $netlistFile)) {
    Write-Host "❌ Netlist file not found: $netlistFile" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $sdcFile)) {
    Write-Host "⚠️  SDC file not found: $sdcFile (will skip SDC loading)" -ForegroundColor Yellow
    $hasSDC = $false
} else {
    $hasSDC = $true
}

Write-Host "Files:" -ForegroundColor Cyan
Write-Host "  Library: $libFile"
Write-Host "  Netlist: $netlistFile"
if ($hasSDC) {
    Write-Host "  SDC: $sdcFile"
}
Write-Host "  Output: $cornerOutputDir"
Write-Host ""

# Convert paths for WSL
$libPathWSL = $libFile -replace '\\', '/' -replace '^D:', '/mnt/d'
$netlistPathWSL = $netlistFile -replace '\\', '/' -replace '^D:', '/mnt/d'
$sdcPathWSL = if ($hasSDC) { $sdcFile -replace '\\', '/' -replace '^D:', '/mnt/d' } else { "" }
$outputDirWSL = $cornerOutputDir -replace '\\', '/' -replace '^D:', '/mnt/d'
$staticDirWSL = (Join-Path $benchmarkOutputDir "static") -replace '\\', '/' -replace '^D:', '/mnt/d'

# Create TCL script for data export
$wslTcl = "/tmp/ot_export_${Benchmark}_${Corner}.tcl"
$tclContent = @"
# Read library
read_celllib $libPathWSL

# Read netlist
read_verilog $netlistPathWSL

# Read SDC constraints
"@

if ($hasSDC) {
    $tclContent += "read_sdc $sdcPathWSL`n"
}

$tclContent += @"

# Update timing
update_timing

# Check clocks (for debugging)
report_clocks

# Export graph structure (DOT format, for cross-check only)
dump_graph -o $staticDirWSL/graph.dot

# Export node dynamic features
dump_at -o $outputDirWSL/arrival.txt
dump_slew -o $outputDirWSL/slew.txt
dump_pin_cap -o $outputDirWSL/pin_cap.txt
dump_pin_static -o $outputDirWSL/pin_static.txt

# Export edge/net features
dump_net_load -o $outputDirWSL/net_load.txt
dump_arc_delay -o $outputDirWSL/arc_delay.txt

# Report timing summary
report_wns
report_tns
"@

$wslCmd = "cat > $wslTcl << 'EOF'
$tclContent
EOF
"

wsl bash -c $wslCmd | Out-Null

Write-Host "Running OpenTimer for data export..." -ForegroundColor Cyan
Write-Host ""

$output = wsl bash -c "cd /mnt/d/opentimer/OpenTimer && timeout 600 ./bin/ot-shell < $wslTcl" 2>&1

# Check for errors
$hasError = $false
$errorLines = @()
$wns = $null
$tns = $null

foreach ($line in ($output -split "`n")) {
    $trimmed = $line.Trim()
    
    if ($trimmed -match '^ERROR|^FATAL|Error|error') {
        $hasError = $true
        $errorLines += $trimmed
    }
    
    # Parse WNS/TNS
    if ($trimmed -match '^-?\d+(\.\d+)?$') {
        if ($null -eq $wns) {
            $wns = [double]$trimmed
        } elseif ($null -eq $tns) {
            $tns = [double]$trimmed
        }
    }
}

Write-Host "============================================"
if ($hasError) {
    Write-Host "❌ OpenTimer encountered errors" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error messages:" -ForegroundColor Yellow
    $errorLines | Select-Object -First 10 | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "✅ OpenTimer export completed!" -ForegroundColor Green
    Write-Host ""
    if ($null -ne $wns) {
        Write-Host "WNS: $wns ns" -ForegroundColor Cyan
    }
    if ($null -ne $tns) {
        Write-Host "TNS: $tns ns" -ForegroundColor Cyan
    }
}

Write-Host ""

# Check exported files
Write-Host "Checking exported files..." -ForegroundColor Cyan
$exportedFiles = @(
    "$staticDirWSL/graph.dot",
    "$outputDirWSL/arrival.txt",
    "$outputDirWSL/slew.txt",
    "$outputDirWSL/pin_cap.txt",
    "$outputDirWSL/net_load.txt",
    "$outputDirWSL/arc_delay.txt"
)

$allFilesExist = $true
foreach ($file in $exportedFiles) {
    $exists = wsl bash -c "test -f $file && echo 'yes' || echo 'no'"
    if ($exists -eq "yes") {
        $size = wsl bash -c "wc -l < $file"
        Write-Host "  ✅ $(Split-Path $file -Leaf): $size lines" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $(Split-Path $file -Leaf): NOT FOUND" -ForegroundColor Red
        $allFilesExist = $false
    }
}

Write-Host ""

# Cleanup
wsl bash -c "rm -f $wslTcl" | Out-Null

if ($allFilesExist) {
    Write-Host "============================================"
    Write-Host "✅ Data export completed successfully!"
    Write-Host ""
    Write-Host "Next step: Run validation script:"
    Write-Host "  python scripts/validate_exported_data.py --benchmark $Benchmark --corner $Corner --output-dir $OutputDir" -ForegroundColor Cyan
    Write-Host "============================================"
} else {
    Write-Host "============================================"
    Write-Host "❌ Some files are missing. Please check OpenTimer output above."
    Write-Host "============================================"
    exit 1
}

