# Simple OpenTimer run for ethmac (WSL)
# Generates a WSL-side TCL file and parses WNS/TNS from ot-shell output.

$libPathWSL = "/mnt/d/bishe_database/BUFLIB/lib_rvt/saed32rvt_tt1p05v25c.lib"
$netlistPathWSL = "/mnt/d/bishe_database/benchmark/netlists/ethmac/ethmac_netlist.v"
$sdcPathWSL = "/mnt/d/bishe_database/benchmark/netlists/ethmac/ethmac.sdc"

$wslTcl = "/tmp/ot_ethmac_simple.tcl"

Write-Host "Creating TCL at $wslTcl" -ForegroundColor Cyan

$createTclCmd = @"
cat <<'EOF' > $wslTcl
read_celllib $libPathWSL
read_verilog $netlistPathWSL
read_sdc $sdcPathWSL
update_timing
report_wns
report_tns
EOF
"@

wsl bash -c $createTclCmd

Write-Host "Running OpenTimer..." -ForegroundColor Cyan
$output = wsl bash -c "cd /mnt/d/opentimer/OpenTimer && timeout 120 ./bin/ot-shell < $wslTcl" 2>&1

Write-Host "Output (last 20 lines):" -ForegroundColor Cyan
$output | Select-Object -Last 20

# Parse WNS/TNS from numeric-only lines.
$numericValues = @()
foreach ($line in ($output -split "`n")) {
    $trimmed = $line.Trim()
    if ($trimmed -match '^-?\d+(\.\d+)?$') {
        $numericValues += [double]$trimmed
    }
}

if ($numericValues.Count -ge 1) {
    Write-Host "" 
    Write-Host "WNS: $($numericValues[0])" -ForegroundColor Green
    if ($numericValues.Count -ge 2) {
        Write-Host "TNS: $($numericValues[1])" -ForegroundColor Green
    } else {
        Write-Host "TNS: N/A (report_tns not captured)" -ForegroundColor Yellow
    }
} else {
    Write-Host "" 
    Write-Host "Could not parse WNS/TNS. See output above." -ForegroundColor Yellow
}

# Cleanup
wsl bash -c "rm -f $wslTcl" | Out-Null
