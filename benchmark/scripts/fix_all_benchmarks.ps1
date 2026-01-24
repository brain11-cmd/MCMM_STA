# Fix all problematic benchmarks (fifo, jpeg, ethmac)
param(
    [string]$FixPortsScript = "D:\bishe_database\benchmark\scripts\fix_ports.py",
    [string]$FixIsolScript = "D:\bishe_database\benchmark\scripts\fix_isolation_cells.py",
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists"
)

$benchmarks = @(
    @{name="fifo"; hasIsol=$true},
    @{name="jpeg"; hasIsol=$false},
    @{name="ethmac"; hasIsol=$false}
)

Write-Host "============================================"
Write-Host "Fixing Problematic Benchmarks"
Write-Host "============================================"

foreach ($bm in $benchmarks) {
    $name = $bm.name
    $netlist = Join-Path $NetlistDir "$name\${name}_netlist.v"
    $fixed1 = Join-Path $NetlistDir "$name\${name}_netlist_fixed.v"
    $fixed2 = Join-Path $NetlistDir "$name\${name}_netlist_final.v"
    
    if (-not (Test-Path $netlist)) {
        Write-Host "[$name] Netlist not found, skipping"
        continue
    }
    
    Write-Host "[$name] Fixing..." -NoNewline
    
    # Step 1: Fix escaped identifiers
    python $FixPortsScript $netlist $fixed1 2>&1 | Out-Null
    
    if (-not (Test-Path $fixed1)) {
        Write-Host " Failed (step 1)"
        continue
    }
    
    # Step 2: Fix isolation cells if needed
    if ($bm.hasIsol) {
        python $FixIsolScript $fixed1 $fixed2 2>&1 | Out-Null
        if (Test-Path $fixed2) {
            Move-Item -Path $fixed2 -Destination $netlist -Force
            Write-Host " OK"
        } else {
            Write-Host " Failed (step 2)"
        }
    } else {
        Move-Item -Path $fixed1 -Destination $netlist -Force
        Write-Host " OK"
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "Done"
Write-Host "============================================"

