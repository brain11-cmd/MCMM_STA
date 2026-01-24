# Re-synthesize benchmarks with fixed script
param(
    [string]$YosysPath = "D:\oss-cad-suite\bin\yosys.exe",
    [string]$LibPath = "D:\bishe_database\BUFLIB\lib_rvt\saed32rvt_tt1p05v25c.lib",
    [string]$RtlDir = "D:\bishe_database\benchmark\rtl_src",
    [string]$OutputDir = "D:\bishe_database\benchmark\netlists",
    [string]$FixScript = "D:\bishe_database\benchmark\scripts\fix_ports.py"
)

# Benchmarks that have RTL and should work
$benchmarks = @(
    @{name="gcd"; top="gcd"; files=@("gcd.v")},
    @{name="uart"; top="uart"; files=@("uart.v", "uart_rx.v", "uart_tx.v")},
    @{name="spi"; top="spi"; files=@("spi.v")},
    @{name="fifo"; top="fifo"; files=@("fifo.v", "fifo1.v", "fifomem.v", "rptr_empty.v", "sync_r2w.v", "sync_w2r.v", "wptr_full.v")},
    @{name="aes"; top="aes_cipher_top"; files=@("aes_cipher_top.v", "aes_inv_cipher_top.v", "aes_inv_sbox.v", "aes_key_expand_128.v", "aes_rcon.v", "aes_sbox.v", "timescale.v")},
    @{name="jpeg"; top="jpeg_encoder"; files=@("jpeg_encoder.v", "dct.v", "dct_cos_table.v", "dct_mac.v", "dctu.v", "dctub.v", "div_su.v", "div_uu.v", "fdct.v", "jpeg_qnr.v", "jpeg_rle.v", "jpeg_rle1.v", "jpeg_rzs.v", "zigzag.v")},
    @{name="ethmac"; top="eth_top"; files=@("eth_top.v", "eth_clockgen.v", "eth_cop.v", "eth_crc.v", "eth_fifo.v", "eth_maccontrol.v", "eth_macstatus.v", "eth_miim.v", "eth_outputcontrol.v", "eth_random.v", "eth_receivecontrol.v", "eth_register.v", "eth_registers.v", "eth_rxaddrcheck.v", "eth_rxcounters.v", "eth_rxethmac.v", "eth_rxstatem.v", "eth_shiftreg.v", "eth_spram_256x32.v", "eth_transmitcontrol.v", "eth_txcounters.v", "eth_txethmac.v", "eth_txstatem.v", "eth_wishbone.v", "ethmac_defines.v", "ethmac.v", "timescale.v")},
    @{name="dynamic_node"; top="dynamic_node_top_wrap"; files=@("dynamic_node.pickle.v")}
)

Write-Host "============================================"
Write-Host "Re-synthesizing Benchmarks with Fixed Script"
Write-Host "============================================"

$successCount = 0
$failCount = 0

foreach ($bm in $benchmarks) {
    $design = $bm.name
    $topModule = $bm.top
    $designDir = Join-Path $RtlDir $design
    
    if (-not (Test-Path $designDir)) {
        Write-Host "[$design] RTL directory not found, skipping"
        continue
    }
    
    Write-Host "[$design] Synthesizing..." -NoNewline
    
    $designOutputDir = Join-Path $OutputDir $design
    New-Item -ItemType Directory -Path $designOutputDir -Force | Out-Null
    
    $netlistFile = Join-Path $designOutputDir "${design}_netlist.v"
    $yosysScript = Join-Path $designOutputDir "synth_fixed.ys"
    
    # Build file list
    $vFilePaths = @()
    foreach ($f in $bm.files) {
        $fullPath = Join-Path $designDir $f
        if (Test-Path $fullPath) {
            $vFilePaths += "read_verilog -sv `"$fullPath`""
        }
    }
    
    if ($vFilePaths.Count -eq 0) {
        Write-Host " No RTL files found"
        $failCount++
        continue
    }
    
    # Generate Yosys script
    $scriptContent = @"
# Yosys synthesis for $design -> SAED32 (Fixed)

$($vFilePaths -join "`n")

hierarchy -check -top $topModule

proc
flatten
opt -full

memory -nomap
memory_dff
memory_map

techmap
dfflibmap -liberty "$LibPath"
abc -liberty "$LibPath"

opt_clean -purge
clean

splitnets -ports

write_verilog -noattr -noexpr -nohex "$netlistFile"
stat -liberty "$LibPath"
"@
    
    # Write without BOM (Yosys doesn't like BOM)
    [System.IO.File]::WriteAllText($yosysScript, $scriptContent, [System.Text.UTF8Encoding]::new($false))
    
    # Run Yosys
    $logFile = Join-Path $designOutputDir "synth_fixed.log"
    $errFile = Join-Path $designOutputDir "synth_fixed_err.log"
    
    try {
        $proc = Start-Process -FilePath $YosysPath -ArgumentList "-s `"$yosysScript`"" `
                              -NoNewWindow -Wait -PassThru `
                              -RedirectStandardOutput $logFile `
                              -RedirectStandardError $errFile
        
        if ($proc.ExitCode -eq 0 -and (Test-Path $netlistFile)) {
            # Fix escaped identifiers
            if (Test-Path $FixScript) {
                $fixedFile = "${netlistFile}.tmp"
                python $FixScript $netlistFile $fixedFile 2>&1 | Out-Null
                if (Test-Path $fixedFile) {
                    Move-Item -Path $fixedFile -Destination $netlistFile -Force
                }
            }
            
            $fileSize = (Get-Item $netlistFile).Length / 1KB
            Write-Host " OK ($([math]::Round($fileSize, 1)) KB)"
            $successCount++
        } else {
            Write-Host " Failed (exit code: $($proc.ExitCode))"
            $failCount++
        }
    } catch {
        Write-Host " Error: $_"
        $failCount++
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "Completed: Success $successCount, Failed $failCount"
Write-Host "============================================"

