# Timing and DFX compatibility are required before bitstream generation.
namespace eval qualification {
    proc timing_summary {report} {
        set start [string first {Design Timing Summary} $report]
        if {$start < 0} {error {Missing design timing summary}}
        set summary [string range $report $start end]
        if {![regexp -line {^\s*((?:[-+]?[0-9]+(?:\.[0-9]+)?\s+){11}[-+]?[0-9]+(?:\.[0-9]+)?)\s*$} $summary unused row]} {
            error {Missing finite setup/hold/pulse-width timing results}
        }
        set values [regexp -all -inline {\S+} $row]
        foreach index {0 1 4 5 8 9} {
            if {[lindex $values $index] < 0} {error {Setup/hold/pulse-width timing failed}}
        }
        foreach index {2 6 10} {
            if {[lindex $values $index] != 0} {error {Violating timing endpoints remain}}
        }
        foreach index {3 7 11} {
            if {[lindex $values $index] <= 0} {error {Empty setup/hold/pulse-width endpoint analysis}}
        }
    }

    proc routed_checkpoint {run directory} {
        open_run $run
        set report [report_timing_summary -report_unconstrained -return_string -file [file join $directory ${run}_timing.rpt]]
        timing_summary $report
        set checkpoint [file join $directory ${run}_routed.dcp]
        write_checkpoint -force $checkpoint
        close_design
        return $checkpoint
    }
}
