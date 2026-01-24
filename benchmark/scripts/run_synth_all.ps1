# ============================================================================
# SAED32 批量综合脚本
# 将所有 RTL benchmark 综合到 SAED32 门级网表
# 注意：综合阶段不需要 SDC，SDC 是给后续 STA 用的
# ============================================================================

param(
    [string]$YosysPath = "D:\oss-cad-suite\bin\yosys.exe",
    [string]$LibPath = "D:\bishe_database\BUFLIB\lib_rvt\saed32rvt_tt1p05v25c.lib",
    [string]$RtlDir = "D:\bishe_database\benchmark\rtl_src",
    [string]$OutputDir = "D:\bishe_database\benchmark\netlists",
    [switch]$PrepareOpenTimer,
    [string]$StubFile = "$(Join-Path $PSScriptRoot '..\\rtl_src\\common\\ip_stubs.v')"
)

# 设计配置：设计名 -> 顶层模块名
$designConfig = @{
    "gcd"          = "gcd"
    "uart"         = "uart"
    "spi"          = "spi"
    "fifo"         = "fifo"
    "chameleon"    = "soc_core"
    "aes"          = "aes_cipher_top"
    "ethmac"       = "eth_top"
    "jpeg"         = "jpeg_encoder"
    "dynamic_node" = "dynamic_node_top_wrap"
    "riscv32i"     = "riscv_top"
    "ariane"       = "ariane"
    "ariane133"    = "ariane"
    "ariane136"    = "ariane"
    "black_parrot" = "black_parrot"
    "bp_be_top"    = "bp_be_top"
    "bp_fe_top"    = "bp_fe_top"
    "swerv"        = "swerv_wrapper"
    "tinyRocket"   = "RocketTile"
    "microwatt"    = "microwatt"
    "coyote"       = "rocket_chip"
    "mock-alu"     = "MockAlu"
}

Write-Host "============================================"
Write-Host "SAED32 批量综合脚本 (无需SDC)"
Write-Host "============================================"
Write-Host "Yosys 路径: $YosysPath"
Write-Host "Liberty 库: $LibPath"
Write-Host "RTL 目录:   $RtlDir"
Write-Host "输出目录:   $OutputDir"
Write-Host ""

# 确保输出目录存在
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$successCount = 0
$failCount = 0

foreach ($design in $designConfig.Keys) {
    $designDir = Join-Path $RtlDir $design
    
    if (-not (Test-Path $designDir)) {
        continue
    }
    
    $topModule = $designConfig[$design]
    # 排除 testbench 文件 (*_tb.v, *_test.v, tb_*.v)
    $vFiles = Get-ChildItem -Path $designDir -Filter "*.v" -File | 
              Where-Object { $_.Name -notmatch '_tb\.v$|_test\.v$|^tb_' }
    
    if ($vFiles.Count -eq 0) {
        continue
    }
    
    Write-Host "[$design] 综合中..." -NoNewline
    
    # 创建输出目录
    $designOutputDir = Join-Path $OutputDir $design
    New-Item -ItemType Directory -Path $designOutputDir -Force | Out-Null
    
    # 生成 Yosys 脚本
    $yosysScript = Join-Path $designOutputDir "synth.ys"
    $netlistFile = Join-Path $designOutputDir "${design}_netlist.v"
    $stubRead = ""
    if (Test-Path $StubFile) {
        $stubRead = "read_verilog -sv `"$StubFile`""
    }
    
    # 简化的 Yosys 综合脚本（不需要SDC）
    $scriptContent = @"
# Yosys synthesis for $design -> SAED32

# 读取所有 Verilog 文件
$stubRead
$(($vFiles | ForEach-Object { "read_verilog -sv `"$($_.FullName)`"" }) -join "`n")

# 设置顶层模块
hierarchy -check -top $topModule

# 综合优化
proc
flatten
opt -full

# ============ 关键修改：处理 Memory ============
# 将 memory 转换为 DFF (必须在 techmap 之前)
memory -nomap
memory_dff
memory_map
# ==============================================

# 技术映射到 SAED32
techmap
dfflibmap -liberty "$LibPath"
abc -liberty "$LibPath"

# 清理优化
opt_clean -purge
clean

# 展开总线端口为单 bit 端口 (OpenTimer 需要)
splitnets -ports

# 输出门级网表 (splitnets 后会有 escaped identifiers)
write_verilog -noattr -noexpr -nohex "$netlistFile"

# 统计信息
stat -liberty "$LibPath"
"@
    
    Set-Content -Path $yosysScript -Value $scriptContent -Encoding UTF8
    
    # 运行 Yosys
    $logFile = Join-Path $designOutputDir "synth.log"
    $errFile = Join-Path $designOutputDir "synth_err.log"
    
    try {
        $proc = Start-Process -FilePath $YosysPath -ArgumentList "-s `"$yosysScript`"" `
                              -NoNewWindow -Wait -PassThru `
                              -RedirectStandardOutput $logFile `
                              -RedirectStandardError $errFile
        
        if ($proc.ExitCode -eq 0 -and (Test-Path $netlistFile)) {
            # 修复 escaped identifiers (OpenTimer 兼容性)
            $fixPortsScript = Join-Path $PSScriptRoot "fix_ports.py"
            if (Test-Path $fixPortsScript) {
                $fixedFile = Join-Path $designOutputDir "${design}_netlist_fixed.v"
                python $fixPortsScript $netlistFile $fixedFile | Out-Null
                if (Test-Path $fixedFile) {
                    Move-Item -Path $fixedFile -Destination $netlistFile -Force
                }
            }

            if ($PrepareOpenTimer) {
                $fixGateScript = Join-Path $PSScriptRoot "fix_gate_netlist.py"
                if (Test-Path $fixGateScript) {
                    python $fixGateScript $netlistFile --remove-print --fix-isolation | Out-Null
                }
            }
            
            $fileSize = (Get-Item $netlistFile).Length / 1KB
            Write-Host (" OK ({0:N1} KB)" -f $fileSize)
            $successCount++
        } else {
            Write-Host " 失败"
            $failCount++
        }
    } catch {
        Write-Host " 错误: $_"
        $failCount++
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "综合完成: 成功 $successCount, 失败 $failCount"
Write-Host "网表输出: $OutputDir"
Write-Host "============================================"
