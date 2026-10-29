# Create additional reconfigurable modules (index 1+) for each partition.
foreach part_config $partition_configs {
    set pname [dict get $part_config partition_name]
    set modules [dict get $part_config modules]
    set num_rms [llength $modules]

    for {set i 1} {$i < $num_rms} {incr i} {
        set rm [lindex $modules $i]
        set rm_cell_name [dict get $rm cell_name]

        current_bd_design [get_bd_designs $design_name]
        create_bd_design -boundary_from_container [get_bd_cells /${pname}/rp] ${pname}_${rm_cell_name}

        set control_base 0
        if {[info exists rp_interface] && $rp_interface eq "memory"} {
            set control_base [dict get $memory_control_offsets $pname]
        }
        utils::create_rm $rm $control_base
        if {[info exists rp_interface] && $rp_interface eq "memory" && ![info exists memory_ddr_windows]} {assign_bd_address}

        validate_bd_design
        save_bd_design

        current_bd_design [get_bd_designs $design_name]
        validate_bd_design
        save_bd_design
    }
}
