* TR-1um IP62 models for ngspice characterization.
* Active includes select immutable OS00 engineering overlays; original PDK model files remain unchanged.
* The MOS overlay only closes the PMOS/PMOSg ngspice terminator typo; no MOS electrical fit is claimed.
* The `.parameters` block is explicit so the calibrated manifest and probes share one model set.
.parameters vthMP  = 0
.parameters vthMN  = 0
.parameters vthMPE = 0
.parameters vthMNE = 0
.parameters magRR  = 1
.parameters magRS  = 1
.parameters magCSIO = 1
.include /Users/yanlu/Documents/TR-1um/libs.tech/spice/models/models_IP62_mos_os00_calibrated.lib
.include /Users/yanlu/Documents/TR-1um/libs.tech/spice/models/models_IP62_cap_os00_calibrated.lib
.include /Users/yanlu/Documents/TR-1um/libs.tech/spice/models/models_IP62_diode_os00_calibrated.lib
.include /Users/yanlu/Documents/TR-1um/libs.tech/spice/models/models_IP62_res_os00_calibrated.lib
