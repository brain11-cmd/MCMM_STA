# Check status of background timing analysis
param(
    [string]$Benchmark = "riscv32i",
    [string]$NetlistDir = "D:\bishe_database\benchmark\netlists"
)

$statusFile = Join-Path $NetlistDir "$Benchmark\timing_status.txt"
$jobInfoFile = Join-Path $NetlistDir "$Benchmark\job_info.json"
$outputFile = Join-Path $NetlistDir "$Benchmark\opentimer_timing_result.txt"

Write-Host "============================================"
Write-Host "Timing Analysis Status: $Benchmark"
Write-Host "============================================"
Write-Host ""

# Check if job info exists
if (Test-Path $jobInfoFile) {
    $jobInfo = Get-Content $jobInfoFile | ConvertFrom-Json
    $job = Get-Job -Id $jobInfo.JobId -ErrorAction SilentlyContinue
    
    if ($job) {
        Write-Host "Job Status: $($job.State)" -ForegroundColor $(if ($job.State -eq "Running") { "Yellow" } elseif ($job.State -eq "Completed") { "Green" } else { "Red" })
        Write-Host "Job ID: $($jobInfo.JobId)" -ForegroundColor Cyan
        Write-Host ""
        
        if ($job.State -eq "Completed") {
            Write-Host "✅ Analysis completed!" -ForegroundColor Green
            Write-Host ""
            
            # Get results
            $result = Receive-Job -Id $jobInfo.JobId
            
            if ($result.Success) {
                Write-Host "Results:" -ForegroundColor Cyan
                Write-Host "  WNS: $($result.WNS) ns" -ForegroundColor $(if ($result.WNS -ge 0) { "Green" } else { "Red" })
                Write-Host "  TNS: $($result.TNS) ns" -ForegroundColor $(if ($result.TNS -ge 0) { "Green" } else { "Red" })
                Write-Host "  Duration: $($result.Duration.ToString('hh\:mm\:ss'))" -ForegroundColor Cyan
            } else {
                Write-Host "⚠️  Could not parse WNS/TNS" -ForegroundColor Yellow
            }
        } elseif ($job.State -eq "Running") {
            Write-Host "⏳ Analysis still running..." -ForegroundColor Yellow
            Write-Host "   Started: $($jobInfo.StartTime)" -ForegroundColor Gray
            $elapsed = (Get-Date) - $jobInfo.StartTime
            Write-Host "   Elapsed: $($elapsed.ToString('hh\:mm\:ss'))" -ForegroundColor Gray
        }
    }
}

# Check status file
if (Test-Path $statusFile) {
    Write-Host ""
    Write-Host "Status file content:" -ForegroundColor Cyan
    Get-Content $statusFile | ForEach-Object {
        Write-Host "  $_" -ForegroundColor White
    }
} else {
    Write-Host "⚠️  Status file not found" -ForegroundColor Yellow
}

# Check output file
if (Test-Path $outputFile) {
    $fileSize = (Get-Item $outputFile).Length / 1KB
    Write-Host ""
    Write-Host "Output file: $outputFile ($([math]::Round($fileSize, 1)) KB)" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "============================================"


