# Optional compatible standard cells from KoheiUchi/TR_1um_sc.
# Source-derived GDS/LEF/SPICE/CDL and functional Verilog are under
# libs.ref/TR-1um_stdcell/aux and the generated LEFs are under lef/.
set ::env(TR1UM_AUX_STD_CELL_LIBRARY) TR-1um_aux_stdcell
set ::env(TR1UM_AUX_LEFS) [list \
  "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/TR-1um_stdcell/lef/DFFQU1.lef" \
  "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/TR-1um_stdcell/lef/FA1D1.lef" \
  "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/TR-1um_stdcell/lef/HA1S.lef"]
set ::env(TR1UM_AUX_GDS) [list \
  "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/TR-1um_stdcell/aux/flow_gds/DFFQU1.gds" \
  "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/TR-1um_stdcell/aux/flow_gds/FA1D1.gds" \
  "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/TR-1um_stdcell/aux/flow_gds/HA1S.gds"]
set ::env(TR1UM_AUX_LIB) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/TR-1um_stdcell/lib/TR-1um_aux_stdcell_typ_5p0V_25C.lib"
