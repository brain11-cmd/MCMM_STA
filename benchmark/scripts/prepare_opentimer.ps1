# Prepare OpenTimer-friendly gate-level netlists for multiple benchmarks.
# 1) Fix escaped identifiers
# 2) Replace unsupported constructs (assign/$print/isolation cells)

param(
    [string[]]$Benchmarks = @(
        "gcd",
        "uart",
        "spi",
        "fifo",
        "aes",
        "jpeg",
        "ethmac",
        "dynamic_node"
    ),
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists"
)

$fixPortsScript = Join-Path $PSScriptRoot "fix_ports.py"
$fixGateScript = Join-Path $PSScriptRoot "fix_gate_netlist.py"

if (-not (Test-Path $fixPortsScript)) {
    Write-Host "Missing fix_ports.py at $fixPortsScript" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $fixGateScript)) {
    Write-Host "Missing fix_gate_netlist.py at $fixGateScript" -ForegroundColor Red
    exit 1
}

Write-Host "============================================"
Write-Host "Prepare OpenTimer Netlists"
Write-Host "============================================"

foreach ($bm in $Benchmarks) {
    $netlist = Join-Path $NetlistDir "$bm\${bm}_netlist.v"

    if (-not (Test-Path $netlist)) {
        Write-Host "[$bm] Netlist not found, skipping" -ForegroundColor Yellow
        continue
    }

    Write-Host "[$bm] Fixing escaped identifiers..." -NoNewline
    $tmpFile = "${netlist}.tmp"

    try {
        python $fixPortsScript $netlist $tmpFile 2>&1 | Out-Null
        if (Test-Path $tmpFile) {
            Move-Item -Path $tmpFile -Destination $netlist -Force
            Write-Host " OK"
        } else {
            Write-Host " Failed (no output)" -ForegroundColor Yellow
            continue
        }
    } catch {
        Write-Host " Error: $_" -ForegroundColor Red
        continue
    }

    Write-Host "[$bm] Replacing assign/$print/isolation cells..." -NoNewline
    try {
        python $fixGateScript $netlist --remove-print --fix-isolation 2>&1 | Out-Null
        Write-Host " OK"
    } catch {
        Write-Host " Error: $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "Done"
Write-Host "============================================"
