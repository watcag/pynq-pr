# Post-placement fit check (YAML `implementation: {place_fit_check: true}`).
#
# Runs as the place_design TCL.POST hook of every implementation run, in the run's directory.
# For each pblock with cells assigned (one per reconfigurable partition), it writes
#   place_fit_<pblock>.rpt      report_utilization -pblocks of the placed design
#   place_fit_<pblock>.txt      sites in the pblock, SLICE/DSP/RAMB/URAM sites the partition's cells
#                               use, and those outside the pblock
# and fails the run, before routing, if a partition's cells sit outside its pblock or the
# pblock is over-utilized (DRC UTLZ-1).

set fit_failures [list]
foreach pblock [get_pblocks -quiet] {
    set roots [get_cells -quiet -of_objects $pblock]
    if {![llength $roots]} {continue}
    set name [get_property NAME $pblock]
    set cells [list]
    foreach root $roots {
        set cells [concat $cells [get_cells -quiet -hierarchical -filter "IS_PRIMITIVE && NAME =~ $root/*"]]
    }
    set available [dict create]
    foreach site [get_sites -quiet -of_objects $pblock] {dict set available $site 1}
    # Only the resource types pynq-pr's pblocks are built from (SLICE, DSP, RAMB, URAM): e.g. a clock
    # buffer of the partition is legally placed outside them.
    set used [list]
    foreach site [lsort -unique [get_sites -quiet -of_objects $cells]] {
        if {[regexp {^(SLICE|DSP|RAMB|URAM)} $site]} {lappend used $site}
    }
    set outside [list]
    foreach site $used {
        if {![dict exists $available $site]} {lappend outside $site}
    }
    report_utilization -pblocks $pblock -file place_fit_${name}.rpt
    set fd [open place_fit_${name}.txt w]
    puts $fd "pblock_sites=[dict size $available] used_sites=[llength $used] outside_sites=[llength $outside]"
    if {[llength $outside]} {puts $fd "outside: [lrange $outside 0 49]"}
    close $fd
    if {[llength $outside]} {
        lappend fit_failures "$name: [llength $outside] used sites outside the pblock"
    }
}
report_drc -checks [get_drc_checks UTLZ-1] -file place_fit_drc.rpt
set utlz [get_drc_violations -quiet -filter {CHECK == "UTLZ-1"}]
if {[llength $utlz]} {
    lappend fit_failures "[llength $utlz] UTLZ-1 over-utilization violations (place_fit_drc.rpt)"
}
if {[llength $fit_failures]} {
    error "Post-placement fit check failed: [join $fit_failures {; }]"
}
