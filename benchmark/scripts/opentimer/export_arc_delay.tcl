# Export arc delay from OpenTimer
# This script should be run after update_timing
# Usage: source export_arc_delay.tcl

# Note: OpenTimer doesn't have a built-in dump_arc_delay command
# This is a placeholder - we'll need to add this functionality to OpenTimer
# or use a workaround

# For now, we'll use dump_ckt which includes arc information
# But it doesn't have the 4-channel delay format we need

# TODO: Add dump_arc_delay command to OpenTimer that exports:
# - src_pin_name, dst_pin_name
# - dRR, dRF, dFR, dFF (4 channels)
# - maskRR, maskRF, maskFR, maskFF (validity masks)
# - edge_type (cell_arc=0, net_arc=1)

puts "Note: dump_arc_delay command not yet implemented in OpenTimer"
puts "This script is a placeholder for future implementation"


