# Test to verify dump_at is called AFTER update_timing
param(
    [string]$Benchmark = "gcd",
    [string]$Corner = "tt0p85v25c",
    [string]$LibPath = "D:\bishe_database\BUFLIB\lib_rvt",
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists"
)

Write-Host "============================================"
Write-Host "Testing Dump Timing Order: $Benchmark"
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

# Create TCL script with explicit order and verification
$wslTcl = "/tmp/ot_order_test_${Benchmark}.tcl"
$tclContent = @"
# Step 1: Read files
read_celllib $libPathWSL
read_verilog $netlistPathWSL
read_sdc $sdcPathWSL

# Step 2: Update timing (MUST be before dump)
update_timing

# Step 3: Verify timing was updated
report_wns
report_tns

# Step 4: Now dump (AFTER update_timing)
dump_at -o /tmp/arrival_test.txt

# Step 5: Check a specific pin that should have arrival
report_at -pin _234_:Y -max -rise
"@

$wslCmd = "cat > $wslTcl << 'EOF'
$tclContent
EOF
"

wsl bash -c $wslCmd | Out-Null

Write-Host "Running OpenTimer with explicit order..." -ForegroundColor Cyan
Write-Host ""

$output = wsl bash -c "cd /mnt/d/opentimer/OpenTimer && timeout 600 ./bin/ot-shell < $wslTcl 2>&1"

Write-Host "OpenTimer Output:" -ForegroundColor Cyan
Write-Host "--------------------------------------------"
$output | ForEach-Object { Write-Host $_ }

Write-Host "--------------------------------------------"
Write-Host ""

# Check arrival.txt for valid values
Write-Host "Checking arrival_test.txt..." -ForegroundColor Cyan
$arrivalContent = wsl bash -c "cat /tmp/arrival_test.txt 2>/dev/null | head -20"
if ($arrivalContent) {
    Write-Host $arrivalContent
    
    # Count n/a vs valid values
    $nACount = ($arrivalContent | Select-String -Pattern '\bn/a\b').Count
    $validCount = ($arrivalContent | Select-String -Pattern '\d+\.\d+').Count
    
    Write-Host ""
    Write-Host "Statistics:" -ForegroundColor Cyan
    Write-Host "  Lines with 'n/a': $nACount"
    Write-Host "  Lines with valid values: $validCount"
    
    if ($validCount -gt 0) {
        Write-Host "  ✅ Found valid arrival values!" -ForegroundColor Green
    } else {
        Write-Host "  ❌ All values are n/a" -ForegroundColor Red
    }
} else {
    Write-Host "  ❌ arrival_test.txt not found or empty" -ForegroundColor Red
}

# Check report_at output
Write-Host ""
Write-Host "Checking report_at output..." -ForegroundColor Cyan
$reportAt = $output | Select-String -Pattern '_234_:Y|report_at'
if ($reportAt) {
    Write-Host $reportAt
} else {
    Write-Host "  ⚠️  No report_at output found"
}

# Cleanup
wsl bash -c "rm -f $wslTcl /tmp/arrival_test.txt" | Out-Null

Write-Host ""
Write-Host "============================================"


