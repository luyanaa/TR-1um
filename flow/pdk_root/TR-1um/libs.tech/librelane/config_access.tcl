set ::env(PROCESS) 1000
set ::env(DEF_UNITS_PER_MICRON) 1000
set ::env(VDD_PIN) "VDD"
set ::env(GND_PIN) "GND"
set ::env(SCL_POWER_PINS) [list VDD]
set ::env(SCL_GROUND_PINS) [list GND]
set ::env(PRIMARY_GDSII_STREAMOUT_TOOL) "klayout"
set ::env(DEFAULT_CORNER) "nom_typ_5p0V_25C"
set ::env(STA_CORNERS) "nom_typ_5p0V_25C"
set ::env(TIMING_VIOLATION_CORNERS) "*"
if { [info exists ::env(TR1UM_USE_BEOL_ACCESS)] && $::env(TR1UM_USE_BEOL_ACCESS) == 1 } {
    set ::env(KLAYOUT_TECH) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/TR-1um_stdcell_access/lef/TR-1um_tech.lef"
    set ::env(KLAYOUT_PROPERTIES) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/klayout/tech/TR-1um.lyp"
    set ::env(KLAYOUT_DRC_RUNSET) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/klayout/tech/drc/run.drc"
    set ::env(KLAYOUT_DEF_LAYER_MAP) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/klayout/tech/def_layer_map.map"
} else {
    set ::env(KLAYOUT_TECH) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/klayout/tech/TR-1um.lyt"
    set ::env(KLAYOUT_PROPERTIES) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/klayout/tech/TR-1um.lyp"
    set ::env(KLAYOUT_DRC_RUNSET) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/klayout/tech/drc/run.drc"
    set ::env(KLAYOUT_DEF_LAYER_MAP) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/klayout/tech/def_layer_map.map"
}
if { [info exists ::env(TR1UM_USE_BEOL_ACCESS)] && $::env(TR1UM_USE_BEOL_ACCESS) == 1 } {
    set ::env(STD_CELL_LIBRARY) TR-1um_stdcell_access
    set ::env(_TR1UM_LIBROOT) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/TR-1um_stdcell_access"
} else {
    set ::env(STD_CELL_LIBRARY) TR-1um_stdcell
    set ::env(_TR1UM_LIBROOT) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/TR-1um_stdcell"
}
set ::env(LIB) [dict create]
if { $::env(STD_CELL_LIBRARY) == "TR-1um_stdcell_access" } {
    dict set ::env(LIB) "*_typ_5p0V_25C" "$::env(_TR1UM_LIBROOT)/lib/TR-1um_stdcell_access_typ_5p0V_25C.lib"
} else {
    dict set ::env(LIB) "*_typ_5p0V_25C" "$::env(_TR1UM_LIBROOT)/lib/TR-1um_stdcell_typ_5p0V_25C.lib"
}
set ::env(TECH_LEFS) [dict create]
if { $::env(STD_CELL_LIBRARY) == "TR-1um_stdcell_access" } {
    dict set ::env(TECH_LEFS) "*" "$::env(_TR1UM_LIBROOT)/lef/TR-1um_tech.lef"
    set ::env(CELL_LEFS) [list "$::env(_TR1UM_LIBROOT)/lef/TR-1um_access_cells.lef"]
    set ::env(CELL_GDS) "$::env(_TR1UM_LIBROOT)/gds/TR-1um_stdcell_access.gds"
    set ::env(CELL_VERILOG_MODELS) "$::env(_TR1UM_LIBROOT)/verilog/TR-1um_stdcell_access.v"
    set ::env(CELL_SPICE_MODELS) "$::env(_TR1UM_LIBROOT)/spice/TR-1um_stdcell_access.spice"
    set ::env(CELL_CDLS) "$::env(_TR1UM_LIBROOT)/cdl/TR-1um_stdcell_access.cdl"
    set ::env(PLACE_SITE) TR1um_access_site
} else {
    dict set ::env(TECH_LEFS) "*" "$::env(_TR1UM_LIBROOT)/lef/TR-1um_tech.lef"
    set ::env(CELL_LEFS) [list "$::env(_TR1UM_LIBROOT)/lef/TR-1um_cells.lef"]
    set ::env(CELL_GDS) "$::env(_TR1UM_LIBROOT)/gds/TR-1um_stdcell.gds"
    set ::env(CELL_VERILOG_MODELS) "$::env(_TR1UM_LIBROOT)/verilog/TR-1um_stdcell.v"
    set ::env(CELL_SPICE_MODELS) "$::env(_TR1UM_LIBROOT)/spice/TR-1um_stdcell.spice"
    set ::env(CELL_CDLS) "$::env(_TR1UM_LIBROOT)/cdl/TR-1um_stdcell.cdl"
    set ::env(PLACE_SITE) TR1um_site
}
set ::env(GPL_CELL_PADDING) 2
set ::env(DPL_CELL_PADDING) 1
set ::env(CELL_PAD_EXCLUDE) [list TIEHI TIELO]
set ::env(FILL_CELLS) [list TIELO]
set ::env(DECAP_CELLS) [list]
set ::env(RT_MIN_LAYER) "M1"
set ::env(IO_PIN_V_LAYER) "M2"
set ::env(IO_PIN_H_LAYER) "M1"
set ::env(FP_TRACKS_INFO) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/tracks.info"
set ::env(SYNTH_DRIVING_CELL) "BUF_X1/A"
set ::env(SYNTH_BUFFER_CELL) "BUF_X1/A/Y"
set ::env(SYNTH_TIEHI_CELL) "TIEHI/HI"
set ::env(SYNTH_TIELO_CELL) "TIELO/LO"
set ::env(CTS_ROOT_BUFFER) "BUF_X1"
set ::env(CTS_CLK_BUFFERS) [list "BUF_X1"]
set ::env(RCX_RULESETS) [dict create]
dict set ::env(RCX_RULESETS) "*" "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/rcx/TR-1um_placeholder.rules"
set ::env(PDN_RAIL_LAYER) "M1"
set ::env(PDN_RAIL_WIDTH) 5
set ::env(PDN_RAIL_OFFSET) 0
set ::env(PDN_CORE_RING_HWIDTH) 5
set ::env(PDN_CORE_RING_VWIDTH) 5
set ::env(PDN_CORE_RING_HSPACING) 5
set ::env(PDN_CORE_RING_VSPACING) 5
set ::env(PDN_VERTICAL_LAYER) "M2"
set ::env(PDN_HORIZONTAL_LAYER) "M2"
set ::env(PDN_HOFFSET) 30
set ::env(PDN_VWIDTH) 5
set ::env(PDN_HWIDTH) 5
set ::env(PDN_VPITCH) 400
set ::env(PDN_HPITCH) 400
set ::env(PDN_VSPACING) 5
set ::env(PDN_HSPACING) 5
set ::env(IO_DELAY_CONSTRAINT) 5
set ::env(OUTPUT_CAP_LOAD) 0.5
set ::env(MAX_FANOUT_CONSTRAINT) 10
set ::env(CLOCK_UNCERTAINTY_CONSTRAINT) 2
set ::env(CLOCK_TRANSITION_CONSTRAINT) 2
set ::env(TIME_DERATING_CONSTRAINT) 0.5
set ::env(SYNTH_EXCLUDED_CELL_FILE) "/dev/null"
set ::env(PNR_EXCLUDED_CELL_FILE) "/dev/null"
set ::env(PDN_CORE_RING_VOFFSET) 10
set ::env(PDN_CORE_RING_HOFFSET) 10
set ::env(GRT_LAYER_ADJUSTMENTS) "0.3,0.3"
set ::env(RT_MAX_LAYER) "M2"
set ::env(PDN_VOFFSET) 30
# The access library uses the same IP62 62.6um site. Its DRC-clean BEOL
# landings are within existing cells; row spacing remains a separate floorplan
# qualification and is not encoded by changing the cell site height.

