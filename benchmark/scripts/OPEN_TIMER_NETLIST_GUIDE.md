# OpenTimer Gate-Level Netlist Prep Guide

This guide describes a reliable path to produce gate-level netlists that OpenTimer
can parse and analyze using the scripts in this repository.

## 1) Synthesize RTL to gate-level netlist

Use `run_synth_all.ps1`. It now supports `-PrepareOpenTimer` to apply OpenTimer
compatibility fixes immediately after synthesis.

```powershell
# Example: synthesize all configured benchmarks and post-process netlists
powershell -ExecutionPolicy Bypass -File .\benchmark\scripts\run_synth_all.ps1 -PrepareOpenTimer
```

Key steps performed by the synthesis flow:
- `memory` + `memory_dff` + `memory_map` to avoid unsupported memories.
- `splitnets -ports` to ensure single-bit ports (OpenTimer requirement).
- `fix_ports.py` to remove escaped identifiers.
- `fix_gate_netlist.py` to replace unsupported constructs (`assign`, `$print`,
  isolation cells) with library cells.
- `rtl_src/common/ip_stubs.v` provides behavioral stubs for common missing RAMs
  and hard macros so Yosys can synthesize large SoC designs.

## 2) If you already have netlists, run the post-processing only

Use `prepare_opentimer.ps1` to apply the OpenTimer compatibility fixes to
existing netlists.

```powershell
powershell -ExecutionPolicy Bypass -File .\benchmark\scripts\prepare_opentimer.ps1 \
  -Benchmarks @("ethmac", "fifo", "jpeg") \
  -NetlistDir "D:\bishe_database\benchmark\netlists"
```

## 3) Optional: verify a netlist loads in OpenTimer

Create a small TCL like the following and run `ot-shell`:

```tcl
read_celllib D:/bishe_database/BUFLIB/lib_rvt/saed32rvt_tt1p05v25c.lib
read_verilog D:/bishe_database/benchmark/netlists/ethmac/ethmac_netlist.v
read_sdc D:/bishe_database/benchmark/netlists/ethmac/ethmac.sdc
update_timing
report_wns
report_tns
```

Then run:

```powershell
wsl bash -c "cd /mnt/d/opentimer/OpenTimer && ./bin/ot-shell < /mnt/d/bishe_database/benchmark/scripts/ot_ethmac.tcl"
```

## Notes
- If a benchmark fails synthesis, start by confirming the top module name in
  `run_synth_all.ps1` and check the generated `synth_err.log` in the netlist
  output directory.
- Large SoC designs may still require blackbox stubs for vendor IP or memories.
