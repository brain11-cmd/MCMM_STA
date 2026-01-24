# OpenTimer test script for aes benchmark

# Read cell library
read_celllib /mnt/d/bishe_database/BUFLIB/lib_rvt/saed32rvt_tt1p05v25c.lib

# Read verilog netlist
read_verilog /mnt/d/bishe_database/benchmark/netlists/aes/aes_netlist.v

# Read SDC constraints
read_sdc /mnt/d/bishe_database/benchmark/netlists/aes/aes.sdc

# Update timing
update_timing

# Report worst negative slack (WNS) - setup time
report_wns

# Report total negative slack (TNS)
report_tns

# Report worst setup path (max analysis, rise)
report_timing -num_paths 5 -max -rise

# Report worst hold path (min analysis, rise)
report_timing -num_paths 5 -min -rise

