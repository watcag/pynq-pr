# Wrap each partition's dummy into a BDC and replace with the first RM.
current_bd_design $design_name
current_bd_instance /

foreach part_config $partition_configs {
    set pname [dict get $part_config partition_name]
    set modules [dict get $part_config modules]
    set first_rm [lindex $modules 0]
    set first_rm_name [dict get $first_rm cell_name]
    set control_base 0
    if {[info exists rp_interface] && $rp_interface eq "memory"} {
        set control [get_bd_intf_pins -of_objects [get_bd_cells /${pname}/dummy] -filter {MODE == Slave && VLNV =~ *:aximm_rtl:*}]
        set mapped [get_bd_addr_segs -addressing -of_objects $control]
        if {[llength $mapped] != 1} {error "Memory RP needs one assigned static control segment: $pname"}
        set control_base [get_property OFFSET [lindex $mapped 0]]
        dict set memory_control_offsets $pname $control_base
    }

    current_bd_design $design_name
    current_bd_instance /${pname}

    group_bd_cells dummy_hier [get_bd_cells dummy]

    current_bd_instance /
    validate_bd_design
    save_bd_design

    create_bd_design -cell [get_bd_cells /${pname}/dummy_hier] ${pname}_${first_rm_name}
    validate_bd_design
    save_bd_design

    current_bd_design $design_name
    current_bd_instance /${pname}

    set new_cell [create_bd_cell -type container -reference ${pname}_${first_rm_name} ${pname}_temp]
    replace_bd_cell [get_bd_cells dummy_hier] $new_cell
    delete_bd_objs [get_bd_cells dummy_hier]
    set_property name rp $new_cell

    current_bd_instance /

    update_compile_order -fileset sources_1
    validate_bd_design
    save_bd_design

    current_bd_design [get_bd_designs ${pname}_${first_rm_name}]

    delete_bd_objs [get_bd_cells dummy]
    utils::create_rm $first_rm $control_base
    if {[info exists rp_interface] && $rp_interface eq "memory"} {assign_bd_address}

    validate_bd_design
    save_bd_design

    current_bd_design [get_bd_designs $design_name]
    upgrade_bd_cells [get_bd_cells /${pname}/rp]
    if {[info exists rp_interface] && $rp_interface eq "memory"} {
        # Lock common routing apertures before enabling DFX. The first RM's
        # smaller register file must not shrink the static route for later RMs.
        assign_bd_address
        foreach intf [get_bd_intf_pins -of_objects [get_bd_cells /${pname}/rp] -filter {VLNV =~ *:aximm_rtl:*}] {
            set apertures {}
            if {[get_property MODE $intf] eq "Slave"} {
                set segments [get_bd_addr_segs -addressing -of_objects $intf]
                foreach segment $segments {set_property RANGE [expr {1 << $control_aperture_bits}] $segment}
            } else {
                set segments [get_bd_addr_segs -of_objects [get_bd_addr_spaces -of_objects $intf]]
            }
            foreach segment $segments {
                set offset [get_property OFFSET $segment]
                set range [get_property RANGE $segment]
                if {$offset eq "" || $range eq ""} {error "Unmapped static address segment $segment"}
                lappend apertures [list $offset $range]
            }
            if {![llength $apertures]} {error "No static address aperture for memory RP interface $intf"}
            set_property APERTURES $apertures $intf
        }
    }
    validate_bd_design
    save_bd_design
}
