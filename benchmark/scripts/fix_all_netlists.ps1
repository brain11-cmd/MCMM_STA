# Fix all netlist files to remove escaped identifiers
$FixScript = "D:\bishe_database\benchmark\scripts\fix_ports.py"

$benchmarks = @("gcd", "uart", "spi", "fifo", "aes", "jpeg", "ethmac", "dynamic_node")

Write-Host "============================================"
Write-Host "Fixing Escaped Identifiers in Netlists"
Write-Host "============================================"

foreach ($bm in $benchmarks) {
    $netlist = "D:\bishe_database\benchmark\netlists\$bm\${bm}_netlist.v"
    
    if (-not (Test-Path $netlist)) {
        Write-Host "[$bm] Netlist not found, skipping"
        continue
    }
    
    Write-Host "[$bm] Fixing..." -NoNewline
    
    $tmpFile = "${netlist}.tmp"
    
    try {
        python $FixScript $netlist $tmpFile 2>&1 | Out-Null
        
        if (Test-Path $tmpFile) {
            Move-Item -Path $tmpFile -Destination $netlist -Force
            Write-Host " OK"
        } else {
            Write-Host " Failed (no output)"
        }
    } catch {
        Write-Host " Error: $_"
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "Done"
Write-Host "============================================"

