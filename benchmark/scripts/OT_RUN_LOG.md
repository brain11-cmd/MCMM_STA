# OpenTimer Run Log

## 2025-01-26 (scaled SDC: 2.0x period)

Commands:
- `./bin/ot-shell < /tmp/ot_fifotest_scaled.tcl`
- `./bin/ot-shell < /tmp/ot_jpegtest_scaled.tcl`
- `./bin/ot-shell < /tmp/ot_ethmactest_scaled.tcl`

Results:
- fifo: WNS -20.6106, TNS -339.349
- jpeg: WNS -0.114577, TNS -7.2654
- ethmac: WNS -0.0687801, TNS -78.2712

## 2025-01-26 (original SDC periods)

Commands:
- `./bin/ot-shell < /tmp/ot_gcd.tcl`
- `./bin/ot-shell < /tmp/ot_uart.tcl`
- `./bin/ot-shell < /tmp/ot_spi.tcl`
- `./bin/ot-shell < /tmp/ot_aes.tcl`
- `./bin/ot-shell < /tmp/ot_dynamic_node.tcl`

Results:
- gcd: WNS 0.0745988, TNS 0
- uart: WNS 0.0375822, TNS 0
- spi: WNS 0.0189784, TNS 0
- aes: WNS 0.00354479, TNS 0
- dynamic_node: WNS 0.0189784, TNS 0

Notes:
- `gcd/uart/spi/aes` SDC files report an `invalid command "\ufeff#"` warning due to a BOM at the start of the file, but OpenTimer still loads the commands and reports WNS/TNS.
