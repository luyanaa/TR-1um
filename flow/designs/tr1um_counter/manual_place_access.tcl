# Verified access-SCL placement for tr1um_counter.
# Coordinates are lower-left cell origins in microns, matching the
# closure-access-verification placement that completed the flow.
set block [ord::get_db_block]
foreach {name x y} {
    _10_ 50.0 75.6
    _11_ 300.0 75.6
    _12_ 550.0 75.6
    _13_ 50.0 151.2
    _14_ 300.0 151.2
    _15_ 550.0 151.2
    _16_ 50.0 226.8
    _17_ 300.0 226.8
    _18_ 550.0 226.8
    _19_ 50.0 302.4
    _20_ 300.0 302.4
    _21_ 550.0 302.4
} {
    set inst [$block findInst $name]
    if {$inst eq ""} {
        error "access manual placement: missing instance $name"
    }
    $inst setLocation [expr {round($x * 1000.0)}] [expr {round($y * 1000.0)}]
    $inst setPlacementStatus FIRM
}
