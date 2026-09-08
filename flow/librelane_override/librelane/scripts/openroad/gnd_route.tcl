puts "\[INFO\] Applying explicit GND special route"
 # Add the explicit GND escape route to the already-loaded post-DRT database.
 # Do not call read_current_odb here: reloading after STA corner setup causes
 # STA-0482 (define_corners must be called before read_liberty).
write_views
add_global_connection -net GND -inst_pattern u_ana -pin_pattern GND
add_global_connection -net GND -pin_pattern GND
global_connect -force
add_sroute_connect -net GND -outerNet GND \
    -layers {M1 M2} \
    -cut_pitch {5400 5400} \
    -metalwidths {3000 3000} \
    -metalspaces {2000 2000} \
    -ongrid {M1 M2}
if { [info exists ::env(SAVE_DEF)] } {
    write_def $::env(SAVE_DEF)
}
if { [info exists ::env(SAVE_ODB)] } {
    write_db $::env(SAVE_ODB)
}
