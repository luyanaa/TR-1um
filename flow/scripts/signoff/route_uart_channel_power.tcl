foreach required {
    UART_TECH_LEF UART_CELL_LEF UART_INPUT_DEF UART_OUTPUT_DEF UART_OUTPUT_ODB
    UART_OUTPUT_LEF UART_GUIDES UART_DRC
} {
    if {![info exists ::env($required)] || $::env($required) eq ""} {
        error "missing environment variable $required"
    }
}

read_lef $::env(UART_TECH_LEF)
read_lef $::env(UART_CELL_LEF)
read_def $::env(UART_INPUT_DEF)
set_routing_layers -signal M1-M2
set_macro_extension 0
set_global_routing_layer_adjustment M1 0.3
set_global_routing_layer_adjustment M2 0.3

global_route -allow_congestion -congestion_iterations 0 -verbose
write_guides $::env(UART_GUIDES)
detailed_route -droute_end_iter 64 -or_seed 42 -verbose 1 \
    -output_drc $::env(UART_DRC)
write_db $::env(UART_OUTPUT_ODB)
write_def $::env(UART_OUTPUT_DEF)
write_abstract_lef $::env(UART_OUTPUT_LEF)
