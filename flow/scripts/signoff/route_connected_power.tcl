# Route TR-1um VDD/GND as ordinary signal wires after a completed LibreLane run.
#
# DRT does not serialize dbWire geometry after a net is converted back to a
# SPECIAL POWER/GROUND net.  Keep the two supplies classified as SIGNAL in this
# derived database/DEF; their electrical meaning is retained by the Verilog/CDL
# contract and by the VDD/GND pin labels in the physical library.

foreach required {
    CONNECTED_POWER_TECH_LEF
    CONNECTED_POWER_CELL_LEF
    CONNECTED_POWER_MACRO_LEF
    CONNECTED_POWER_INPUT_DEF
    CONNECTED_POWER_OUTPUT_DEF
    CONNECTED_POWER_OUTPUT_ODB
    CONNECTED_POWER_GUIDES
    CONNECTED_POWER_DRC
} {
    if {![info exists ::env($required)] || $::env($required) eq ""} {
        error "missing environment variable $required"
    }
}

read_lef $::env(CONNECTED_POWER_TECH_LEF)
read_lef $::env(CONNECTED_POWER_CELL_LEF)
read_lef $::env(CONNECTED_POWER_MACRO_LEF)
read_def $::env(CONNECTED_POWER_INPUT_DEF)

set block [ord::get_db_block]
set macro_instance "u_ana"
if {[info exists ::env(CONNECTED_POWER_MACRO_INSTANCE)]} {
    set macro_instance $::env(CONNECTED_POWER_MACRO_INSTANCE)
}

set_routing_layers -signal M1-M2
set_macro_extension 0
global_route -start_incremental

# The analog macro has two physically separate GND conductors.  The routing
# LEF calls the body-pad escape GNDP, preventing DRT from choosing only one of
# two geometries that would otherwise belong to the same abstract terminal.
set macro [$block findInst $macro_instance]
if {$macro == "NULL"} {
    error "missing analog macro instance $macro_instance"
}
set gnd_net [$block findNet GND]
if {$gnd_net == "NULL"} {
    error "missing GND net"
}
set gndp [$macro findITerm GNDP]
if {$gndp == "NULL"} {
    error "missing $macro_instance/GNDP routing terminal"
}
$gndp connect $gnd_net
puts "CONNECTED $macro_instance/GNDP -> GND"

foreach name {VDD GND} {
    set net [$block findNet $name]
    if {$net == "NULL"} {
        error "missing supply net $name"
    }
    puts "SUPPLY_BEFORE $name sigtype=[$net getSigType] special=[$net isSpecial]"
    $net setSigType SIGNAL
    $net clearSpecial
    foreach iterm [$net getITerms] {
        set mterm [$iterm getMTerm]
        if {[$mterm getSigType] != "SIGNAL"} {
            $mterm setSigType SIGNAL
        }
    }
    puts "SUPPLY_ROUTE  $name sigtype=[$net getSigType] special=[$net isSpecial]"
}

global_route -end_incremental -allow_congestion -congestion_iterations 0 -verbose
write_guides $::env(CONNECTED_POWER_GUIDES)
detailed_route -droute_end_iter 64 -or_seed 42 -verbose 1 \
    -output_drc $::env(CONNECTED_POWER_DRC)

foreach name {VDD GND} {
    set net [$block findNet $name]
    puts "SUPPLY_OUTPUT $name sigtype=[$net getSigType] special=[$net isSpecial]"
}

write_db $::env(CONNECTED_POWER_OUTPUT_ODB)
write_def $::env(CONNECTED_POWER_OUTPUT_DEF)
