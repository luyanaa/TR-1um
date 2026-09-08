* TR-1um IP62 models for ngspice characterization.
* Fixes two PDK data issues for ngspice:
*   1) `.ends PMOSg` typo -> `.ends PMOS` (models_IP62_mos_v2.lib)
*   2) the `.parameters` block must be present (ip62_models)
.parameters vthMP  = 0
.parameters vthMN  = 0
.parameters vthMPE = 0
.parameters vthMNE = 0
.parameters magRR  = 1
.parameters magRS  = 1
.parameters magCSIO = 1
.include /Users/yanlu/Documents/TR-1um/flow/char/mos_fixed.lib
.include /Users/yanlu/Documents/TR-1um/libs.tech/spice/models/models_IP62_cap_v5p1.lib
.include /Users/yanlu/Documents/TR-1um/libs.tech/spice/models/models_IP62_diode_v2.lib
.include /Users/yanlu/Documents/TR-1um/libs.tech/spice/models/models_IP62_res_v5.lib
