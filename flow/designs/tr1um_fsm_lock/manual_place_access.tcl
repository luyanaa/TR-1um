# Deterministic placement for the TR-1um BEOL-access cells.
#
# Access cells are individually DRC-clean, but placing occupied rows directly
# against one another can create AP/WN interactions at the shared 75.6um row
# boundary. Use every second row, keep every cell R0, and leave a horizontal
# gap. The design still fits comfortably in the 2300um x 1965.6um core.
set block [ord::get_db_block]

set x_min 100000
set x_max 2300000
set y_min 75600
set row_pitch 151200
set horizontal_gap 40000
set max_rows 13

set instance_names {}
foreach inst [$block getInsts] {
    lappend instance_names [$inst getName]
}

# Divide the netlist into equally sized chunks so all available sparse rows
# are used.  Center each row independently; this avoids the old behavior of
# filling a few rows from the lower-left corner while retaining deterministic
# placement and the FEOL-safe empty physical row between occupied rows.
set sorted_names [lsort $instance_names]
set cell_count [llength $sorted_names]
set cells_per_row [expr {int(ceil(double($cell_count) / $max_rows))}]
set available_width [expr {$x_max - $x_min}]

for {set row 0} {$row < $max_rows} {incr row} {
    set row_names($row) {}
    set row_width($row) 0
}

set index 0
foreach name $sorted_names {
    set row [expr {$index / $cells_per_row}]
    if {$row >= $max_rows} {
        error "TR-1um access placement needs more than $max_rows sparse rows"
    }
    set inst [$block findInst $name]
    set width [[$inst getMaster] getWidth]
    if {[llength $row_names($row)] > 0} {
        set row_width($row) [expr {$row_width($row) + $horizontal_gap}]
    }
    lappend row_names($row) $name
    set row_width($row) [expr {$row_width($row) + $width}]
    incr index
}

set rows_used 0
for {set row 0} {$row < $max_rows} {incr row} {
    if {[llength $row_names($row)] == 0} {
        continue
    }
    if {$row_width($row) > $available_width} {
        error "TR-1um access placement row $row is wider than the placement area"
    }
    incr rows_used
    set x [expr {int(($x_min + ($available_width - $row_width($row)) / 2) / 100) * 100}]
    set y [expr {$y_min + $row * $row_pitch}]
    foreach name $row_names($row) {
        set inst [$block findInst $name]
        set width [[$inst getMaster] getWidth]
        $inst setOrient R0
        $inst setLocation $x $y
        $inst setPlacementStatus FIRM
        set x [expr {$x + $width + $horizontal_gap}]
    }
}

puts "\[INFO\] TR-1um access placement: $cell_count cells centered across $rows_used sparse R0 rows"
