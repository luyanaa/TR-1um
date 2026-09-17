foreach required {
    CORE_TECH_LEF CORE_CELL_LEF CORE_INPUT_DEF CORE_OUTPUT_DEF CORE_OUTPUT_ODB
    CORE_OUTPUT_LEF CORE_GUIDES CORE_DRC
} {
    if {![info exists ::env($required)] || $::env($required) eq ""} {
        error "missing environment variable $required"
    }
}

read_lef $::env(CORE_TECH_LEF)
read_lef $::env(CORE_CELL_LEF)
read_def $::env(CORE_INPUT_DEF)
set_routing_layers -signal M1-M2
set_macro_extension 0
set_global_routing_layer_adjustment M1 0.3
set_global_routing_layer_adjustment M2 0.3

global_route -allow_congestion -congestion_iterations 0 -verbose
write_guides $::env(CORE_GUIDES)
set drt_seed 42
if {[info exists ::env(CORE_DRT_SEED)] && $::env(CORE_DRT_SEED) ne ""} {
    set drt_seed $::env(CORE_DRT_SEED)
}
detailed_route -droute_end_iter 64 -or_seed $drt_seed -verbose 1 -clean_patches \
    -output_drc $::env(CORE_DRC)
write_db $::env(CORE_OUTPUT_ODB)
write_def $::env(CORE_OUTPUT_DEF)
write_abstract_lef $::env(CORE_OUTPUT_LEF)
