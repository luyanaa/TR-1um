# TR-1um RCX: reproducible uniform per-layer engineering estimate.
#
# Tokai Rika's open IP62 reference manual lists parasitic extraction as
# unavailable. The values below are therefore not foundry-qualified PEX; they
# are derived from the checked-in technology LEF and are used consistently by
# placement/timing estimation and the generated SPEF:
#   R' = Rsheet / nominal width
#   C' = Carea * nominal width + 2 * Cedge
# M1: 0.050 ohm/sq, 1.8um, 0.035 fF/um^2, 0.050 fF/um -> 0.0277778 ohm/um, 0.163 fF/um.
# M2: 0.030 ohm/sq, 3.0um, 0.0175 fF/um^2, 0.050 fF/um -> 0.0100000 ohm/um, 0.1525 fF/um.
# Via resistance is not published; OpenROAD's technology LEF has no via R, so
# the nominal estimator leaves it at 0 ohm. This is a known limitation; via-R
# sensitivity is covered by flow/scripts/analysis/rc_sensitivity.py only when a via-R
# model is available.
 source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
 read_lefs "RCX_LEF"
 read_def $::env(CURRENT_DEF)
 set_global_vars
 read_liberty [lindex $::env(LIB) end]
 set_propagated_clock [all_clocks]
 source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl
 
 set_layers_default_rc [lln::get_corner_names]
 set_vias_default_r [lln::get_corner_names]
 
 estimate_parasitics -placement -spef_file $::env(SAVE_SPEF)
