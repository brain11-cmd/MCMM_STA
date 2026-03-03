# Test timing propagation and check for errors
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

# Create TCL script with detailed reporting
$wslTcl = "/tmp/ot_timing_test_${Benchmark}.tcl"
$tclContent = @"
# Read library
read_celllib $libPathWSL

# Read netlist
read_verilog $netlistPathWSL

# Read SDC constraints
read_sdc $sdcPathWSL

# Report clock information
puts "=== Clock Information ==="
report_timing -num_paths 0

# Update timing
puts "=== Updating Timing ==="
update_timing

# Report timing summary
puts "=== Timing Summary ==="
report_wns
report_tns
report_fep

# Check a few pins for arrival time
puts "=== Sample Pin Arrival Times ==="
# Try to report arrival for a few pins
"@

# Try to get some pin names from the netlist
$netlistContent = Get-Content $netlistFile -TotalCount 100
$pinSamples = @()
foreach ($line in $netlistContent) {
    if ($line -match '\.(\w+)\s*\(') {
        $pinName = $matches[1]
        if ($pinName -notmatch '^(input|output|wire|reg|module|endmodule)$') {
            $pinSamples += $pinName
            if ($pinSamples.Count -ge 5) { break }
        }
    }
}

# Add sample pin reports
if ($pinSamples.Count -gt 0) {
    foreach ($pin in $pinSamples[0..2]) {
        $tclContent += "`nreport_at -pin $pin -max -rise"
    }
}

$wslCmd = "cat > $wslTcl << 'EOF'
$tclContent
EOF
"

wsl bash -c $wslCmd | Out-Null

Write-Host "Running OpenTimer with detailed output..." -ForegroundColor Cyan
Write-Host ""

$output = wsl bash -c "cd /mnt/d/opentimer/OpenTimer && timeout 600 ./bin/ot-shell < $wslTcl" 2>&1

Write-Host "============================================"
Write-Host "OpenTimer Output:"
Write-Host "============================================"
$output | ForEach-Object {
    Write-Host $_
}

Write-Host ""
Write-Host "============================================"

# Check for specific issues
$hasError = $false
$hasClock = $false
$hasWNS = $false

foreach ($line in ($output -split "`n")) {
    $trimmed = $line.Trim()
    
    if ($trimmed -match 'ERROR|FATAL|Error|error') {
        $hasError = $true
        Write-Host "❌ Error found: $trimmed" -ForegroundColor Red
    }
    
    if ($trimmed -match 'clock|Clock|CLK') {
        $hasClock = $true
    }
    
    if ($trimmed -match '^-?\d+(\.\d+)?$') {
        $hasWNS = $true
        Write-Host "WNS/TNS value: $trimmed" -ForegroundColor Cyan
    }
}

Write-Host ""
if (-not $hasError -and $hasWNS) {
    Write-Host "✅ Timing propagation appears successful" -ForegroundColor Green
} elseif (-not $hasClock) {
    Write-Host "⚠️  Warning: No clock information found" -ForegroundColor Yellow
    Write-Host "   This may indicate clock constraint issues" -ForegroundColor Yellow
} else {
    Write-Host "⚠️  Warning: Timing propagation may have issues" -ForegroundColor Yellow
}

# Cleanup
wsl bash -c "rm -f $wslTcl" | Out-Null

Write-Host ""
Write-Host "============================================"


