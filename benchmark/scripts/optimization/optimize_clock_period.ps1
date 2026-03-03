# Script to find optimal clock period for AES design
param(
    [string]$YosysPath = "D:\oss-cad-suite\bin\yosys.exe",
    [string]$LibPath = "D:\bishe_database\BUFLIB\lib_rvt\saed32rvt_tt1p05v25c.lib",
    [string]$NetlistPath = "D:\bishe_database\benchmark\netlists\aes\aes_netlist.v",
    [string]$OutputDir = "D:\bishe_database\benchmark\netlists\aes",
    [double]$StartPeriod = 1.0,
    [double]$EndPeriod = 0.1,
    [double]$Step = 0.1
)

$OpenTimerPath = "D:\opentimer\OpenTimer\bin\ot-shell"
$TestScript = Join-Path $OutputDir "test_clock_period.tcl"
$ResultsFile = Join-Path $OutputDir "clock_period_results.txt"

Write-Host "============================================"
Write-Host "Finding Optimal Clock Period for AES"
Write-Host "============================================"
Write-Host "Testing clock periods from $StartPeriod ns to $EndPeriod ns (step: $Step ns)"
Write-Host ""

$results = @()

for ($period = $StartPeriod; $period -ge $EndPeriod; $period -= $Step) {
    $period = [math]::Round($period, 2)
    
    # Generate SDC with new clock period
    $sdcContent = @"
# SDC for aes design - Optimized
# Clock period: ${period}ns
create_clock -period $period -name clk [get_ports clk]

# Input constraints
set_input_delay 0 -clock clk [all_inputs]
set_input_transition 0.1 [all_inputs]

# Output constraints  
set_output_delay 0 -clock clk [all_outputs]
set_load 0.01 [all_outputs]
"@
    
    $sdcFile = Join-Path $OutputDir "aes_${period}ns.sdc"
    Set-Content -Path $sdcFile -Value $sdcContent -Encoding UTF8
    
    # Generate OpenTimer test script
    $testContent = @"
read_celllib /mnt/d/bishe_database/BUFLIB/lib_rvt/saed32rvt_tt1p05v25c.lib
read_verilog /mnt/d/bishe_database/benchmark/netlists/aes/aes_netlist.v
read_sdc /mnt/d/bishe_database/benchmark/netlists/aes/aes_${period}ns.sdc
update_timing
report_wns
report_tns
"@
    
    Set-Content -Path $TestScript -Value $testContent -Encoding UTF8
    
    # Run OpenTimer
    Write-Host "Testing period: $period ns" -NoNewline
    
    try {
        $output = wsl bash -c "cd /mnt/d/opentimer/OpenTimer && ./bin/ot-shell < $TestScript" 2>&1 | Select-String -Pattern "^\d+\.\d+$|^-?\d+$" | Select-Object -First 2
        
        if ($output.Count -ge 2) {
            $wns = [double]$output[0].Line
            $tns = [double]$output[1].Line
            
            $status = if ($wns -ge 0 -and $tns -eq 0) { "PASS" } else { "FAIL" }
            $freq = [math]::Round(1000.0 / $period, 2)
            
            Write-Host " -> WNS: $wns ns, TNS: $tns ns, Freq: $freq MHz [$status]"
            
            $results += [PSCustomObject]@{
                Period = $period
                Frequency = $freq
                WNS = $wns
                TNS = $tns
                Status = $status
            }
            
            # If timing fails, stop testing smaller periods
            if ($status -eq "FAIL") {
                Write-Host "Timing violation detected. Stopping search."
                break
            }
        } else {
            Write-Host " -> Error parsing output"
        }
    } catch {
        Write-Host " -> Error: $_"
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "Results Summary"
Write-Host "============================================"
$results | Format-Table -AutoSize

# Save results
$results | Export-Csv -Path $ResultsFile -NoTypeInformation
Write-Host "Results saved to: $ResultsFile"

# Find optimal period (smallest period with PASS)
$optimal = $results | Where-Object { $_.Status -eq "PASS" } | Sort-Object Period -Descending | Select-Object -First 1

if ($optimal) {
    Write-Host ""
    Write-Host "============================================"
    Write-Host "Recommended Configuration"
    Write-Host "============================================"
    Write-Host "Optimal Clock Period: $($optimal.Period) ns"
    Write-Host "Maximum Frequency: $($optimal.Frequency) MHz"
    Write-Host "WNS: $($optimal.WNS) ns"
    Write-Host ""
    Write-Host "SDC file: aes_$($optimal.Period)ns.sdc"
}


