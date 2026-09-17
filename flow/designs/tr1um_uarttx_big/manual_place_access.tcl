# Deterministic placement for the TR-1um BEOL-access cells.
#
# Access cells are individually DRC-clean, but placing occupied rows directly
# against one another can create AP/WN interactions at the shared 75.6um row
# boundary. Use every second row, keep every cell R0, and leave a horizontal
# gap. The placement fails explicitly if the mapped design exceeds the seven-row
# capacity of the compact core.
set block [ord::get_db_block]

set x_min 62000
set x_max 958000
set y_min 75600
set row_pitch 151200
set horizontal_gap 10000
set max_rows 7

set instance_names {}
foreach inst [$block getInsts] {
    lappend instance_names [$inst getName]
}

# Divide the optimized netlist over seven compact rows in the requested
# 1000um by 1000um macro. A design-local
# GDS postprocessor joins the same-potential PMOS wells across those gaps;
# Five intervals retain an empty 75.6um row. The last pair is adjacent so all
# seven rows remain on the legal site grid and fit below y=982.8um.
# Keep synthesis order as a lightweight connectivity hint. Yosys numbers the
# cells while lowering related logic; contiguous groups generally produce much
# shorter local routes than a longest-cell-first scatter.
set sorted_names [lsort -dictionary $instance_names]
set total_cell_width 0
foreach name $instance_names {
    set inst [$block findInst $name]
    set width [[$inst getMaster] getWidth]
    set cell_width($name) $width
    set total_cell_width [expr {$total_cell_width + $width}]
}
set cell_count [llength $sorted_names]
set available_width [expr {$x_max - $x_min}]

for {set row 0} {$row < $max_rows} {incr row} {
    set row_names($row) {}
    set row_width($row) 0
}

# Exact linear partition: minimize the widest of seven contiguous groups.
# dp(r,j) is the minimum possible maximum width when the first j cells occupy
# r rows; cut(r,j) records the start of the final row.
set prefix_width(0) 0
for {set index 0} {$index < $cell_count} {incr index} {
    set name [lindex $sorted_names $index]
    set prefix_width([expr {$index + 1}]) [expr {$prefix_width($index) + $cell_width($name)}]
}
set dp(0,0) 0
for {set partitions 1} {$partitions <= $max_rows} {incr partitions} {
    set previous_partitions [expr {$partitions - 1}]
    for {set end $partitions} {$end <= $cell_count} {incr end} {
        set best 1000000000000
        set best_cut -1
        for {set start [expr {$partitions - 1}]} {$start < $end} {incr start} {
            if {![info exists dp($previous_partitions,$start)]} {
                continue
            }
            set segment [expr {$prefix_width($end) - $prefix_width($start) + $horizontal_gap * ($end - $start - 1)}]
            set previous $dp($previous_partitions,$start)
            set candidate [expr {$previous > $segment ? $previous : $segment}]
            if {$candidate < $best} {
                set best $candidate
                set best_cut $start
            }
        }
        set dp($partitions,$end) $best
        set cut($partitions,$end) $best_cut
    }
}

if {$dp($max_rows,$cell_count) > $available_width} {
    error "optimal contiguous placement needs $dp($max_rows,$cell_count)nm per row but only ${available_width}nm is available"
}
set end $cell_count
for {set partitions $max_rows} {$partitions >= 1} {incr partitions -1} {
    set start $cut($partitions,$end)
    set row [expr {$partitions - 1}]
    for {set index $start} {$index < $end} {incr index} {
        set name [lindex $sorted_names $index]
        if {[llength $row_names($row)] > 0} {
            set row_width($row) [expr {$row_width($row) + $horizontal_gap}]
        }
        lappend row_names($row) $name
        set row_width($row) [expr {$row_width($row) + $cell_width($name)}]
    }
    set end $start
}

set rows_used 0
for {set row 0} {$row < $max_rows} {incr row} {
    if {[llength $row_names($row)] == 0} {
        continue
    }
    if {$row_width($row) > $available_width} {
        error "large UART access placement row $row is wider than the placement area"
    }
    incr rows_used
    set x [expr {int(($x_min + ($available_width - $row_width($row)) / 2) / 100) * 100}]
    # Half-pitch staggering avoids deterministic access alignment. Row 2 gets
    # the positive phase to clear the _067_ vertical M2 channel near x=285um.
    if {$row == 0 || $row == 2} {
        set x [expr {$x + 2700}]
    } elseif {[expr {$row % 2}] == 1} {
        set x [expr {$x - 2700}]
    }
    set y [expr {$y_min + $row * $row_pitch}]
    if {$row == 6} {
        set y 907200
    }
    foreach name $row_names($row) {
        set inst [$block findInst $name]
        set width [[$inst getMaster] getWidth]
        $inst setOrient R0
        $inst setLocation $x $y
        $inst setPlacementStatus FIRM
        set x [expr {$x + $width + $horizontal_gap}]
    }
}

puts "\[INFO\] Large UART access placement: $cell_count cells centered across $rows_used sparse R0 rows"
