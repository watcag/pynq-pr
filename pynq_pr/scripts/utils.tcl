# Utility procs shared across pynq-pr TCL scripts.

namespace eval utils {

    # Apply Verilog parameters to a BD cell.
    proc apply_rm_params { cell params } {
        if { [dict size $params] > 0 } {
            set prop_list [list]
            dict for {key val} $params {
                lappend prop_list "CONFIG.$key" "$val"
            }
            set_property -dict $prop_list $cell
        }
    }

    # Shared metadata admission for fixed and reconfigurable memory-master IPs.
    proc create_memory_ip {module {allow_multiple 0}} {
        set name [dict get $module cell_name]
        set cell [create_bd_cell -type ip -vlnv [dict get $module vlnv] $name]
        apply_rm_params $cell [dict get $module parameters]
        set masters [get_bd_intf_pins -of_objects $cell -filter {MODE == Master && VLNV =~ *:aximm_rtl:*}]
        set slaves [get_bd_intf_pins -of_objects $cell -filter {MODE == Slave && VLNV =~ *:aximm_rtl:*}]
        set clocks [get_bd_pins -of_objects $cell -filter {TYPE == clk && DIR == I}]
        set resets [get_bd_pins -of_objects $cell -filter {TYPE == rst && DIR == I}]
        if {[llength $masters] < 1 || [llength $masters] > 16 || (!$allow_multiple && [llength $masters] != 1) || [llength $slaves] != 1 || [llength $clocks] != 1 || [llength $resets] != 1} {
            error "Memory IP needs exactly one AXI master, AXI-Lite slave, clock and reset: $name"
        }
        set master [lindex $masters 0]
        set slave [lindex $slaves 0]
        foreach candidate $masters {
            if {[get_property CONFIG.PROTOCOL $candidate] ne "AXI4" ||
                [get_property CONFIG.ADDR_WIDTH $candidate] != 64} {
                error "Memory IP master protocol/address does not match RP: $name"
            }
        }
        if {[get_property CONFIG.PROTOCOL $slave] ne "AXI4LITE" ||
            [get_property CONFIG.DATA_WIDTH $slave] != 32 ||
            [get_property CONFIG.ADDR_WIDTH $slave] > 32} {
            error "Memory IP AXI protocol/address or control aperture does not match RP: $name"
        }
        if {[get_property CONFIG.POLARITY [lindex $resets 0]] ne "ACTIVE_LOW"} {
            error "Memory IP reset must be active low: $name"
        }
        set native_width [get_property CONFIG.ADDR_WIDTH $slave]
        set segments [get_bd_addr_segs -of_objects $slave]
        if {[llength $segments] != 1} {error "Memory IP needs one control register segment: $name"}
        set native_range [expr {min(1 << $native_width, [get_property RANGE [lindex $segments 0]])}]
        if {$native_range <= 0 || ($native_range & ($native_range-1))} {
            error "Native control register aperture must be a positive power of two: $name"
        }
        return [dict create cell $cell master $master masters $masters slave $slave clock [lindex $clocks 0] \
            reset [lindex $resets 0] segment [lindex $segments 0] range $native_range]
    }

    # Board code supplies actual PS DDR target objects. No address is selected
    # from a solver/case, and no peripheral is included by automatic assignment.
    proc checked_memory_windows {windows} {
        set result {}
        foreach window $windows {
            foreach key {segment offset range} {
                if {![dict exists $window $key]} {error "Incomplete DDR window: $key"}
            }
            set offset [dict get $window offset]
            set range [dict get $window range]
            if {![string is entier -strict $offset] || ![string is entier -strict $range] ||
                $offset < 0 || $range <= 0 || ($range & ($range-1)) || ($offset % $range) ||
                $offset+$range > (1 << 64)} {error "Invalid DDR window: $window"}
            lappend result [dict replace $window offset [expr {$offset+0}] range [expr {$range+0}]]
        }
        if {![llength $result]} {error "No authoritative DDR windows"}
        set result [lsort -command {apply {{a b} {expr {[dict get $a offset] < [dict get $b offset] ? -1 : [dict get $a offset] > [dict get $b offset]}}}} $result]
        set end -1
        foreach window $result {
            if {[dict get $window offset] < $end} {error "Overlapping DDR windows"}
            set end [expr {[dict get $window offset]+[dict get $window range]}]
        }
        return $result
    }

    proc require_memory_coverage {expected actual required_bytes} {
        if {![string is entier -strict $required_bytes] || $required_bytes <= 0} {error "Invalid fixed BO envelope"}
        if {[memory_window_pairs $expected] ne [memory_window_pairs $actual]} {
            error "Master DDR windows do not match the complete static DDR windows"
        }
        # The KV host allocates in the low PS DDR/CMA aperture. A large high
        # DDR window cannot compensate for a truncated low decoder route.
        set low [lindex [checked_memory_windows $expected] 0]
        if {[dict get $low offset] != 0 || [dict get $low range] < $required_bytes} {
            error "Low DDR window does not hold the complete fixed BO envelope"
        }
    }

    proc memory_windows_from_segments {segments} {
        set windows {}
        foreach segment $segments {
            lappend windows [dict create segment $segment offset [get_property OFFSET $segment] \
                range [get_property RANGE $segment]]
        }
        return [checked_memory_windows $windows]
    }

    proc memory_window_pairs {windows} {
        set pairs {}
        foreach window [checked_memory_windows $windows] {
            lappend pairs offset [dict get $window offset] range [dict get $window range]
        }
        return $pairs
    }

    # Construction only: explicitly map full DDR windows and exclude every
    # board-declared non-DDR target. The reporting/admission probe never calls it.
    proc map_memory_ddr {master windows exclusions} {
        set windows [checked_memory_windows $windows]
        set spaces [get_bd_addr_spaces -of_objects $master]
        if {![llength $spaces]} {error "Memory master has no address space: $master"}
        foreach space $spaces {
            set end 0
            foreach window $windows {set end [expr {max($end,[dict get $window offset]+[dict get $window range])}]}
            set range 1
            while {$range < $end} {set range [expr {$range << 1}]}
            if {[get_property RANGE $space] < $range} {set_property RANGE $range $space}
            set old [get_bd_addr_segs -of_objects $space]
            if {[llength $old]} {delete_bd_objs $old}
            set index 0
            foreach window $windows {
                create_bd_addr_seg -offset [dict get $window offset] -range [dict get $window range] \
                    $space [dict get $window segment] ddr_$index
                incr index
            }
            foreach target $exclusions {exclude_bd_addr_seg -target_address_space $space $target}
            puts "MEMORY_DDR_MAP master=$master space=$space windows=[memory_window_pairs $windows] excluded=$exclusions"
        }
    }

    # The external master port is represented by a virtual slave segment.
    # UG835's -external/-dict maps separate real DDR windows through that port;
    # leaving its inferred 64 KiB Reg default silently narrows the aperture.
    proc map_external_memory_ddr {masters port windows} {
        set pairs [memory_window_pairs $windows]
        set segments [get_bd_addr_segs -of_objects $port]
        if {[llength $segments] != 1} {error "Expected one external memory virtual segment: $port"}
        foreach master $masters {
            set spaces [get_bd_addr_spaces -of_objects $master]
            if {![llength $spaces]} {error "Memory master has no address space: $master"}
            foreach space $spaces {
                set old [get_bd_addr_segs -of_objects $space]
                if {[llength $old]} {delete_bd_objs $old}
                set mapped [assign_bd_address -external -dict $pairs -target_address_space $space [lindex $segments 0]]
                if {![llength $mapped]} {error "External DDR mapping failed: $space"}
                puts "MEMORY_EXTERNAL_DDR_MAP space=$space windows=$pairs"
            }
        }
    }

    # A PS PLL/divider can resolve slightly away from its requested MHz.
    # Use the connected boundary clock, not an IP's packaging default, as the
    # metadata authority. This does not change the requested timing target.
    proc bind_memory_ip_clock {ip clock_port} {
        set hz [get_property CONFIG.FREQ_HZ $clock_port]
        if {![string is integer -strict $hz] || $hz <= 0} {
            error "Memory RP requires a resolved positive integer clock frequency: $clock_port"
        }
        puts "MEMORY_IP_CLOCK_BIND boundary=$clock_port frequency_hz=$hz"
        foreach endpoint [concat [list [dict get $ip clock] [dict get $ip slave]] [dict get $ip masters]] {
            if {[get_property CONFIG.FREQ_HZ $endpoint] ne $hz} {
                set_property CONFIG.FREQ_HZ $hz $endpoint
            }
            if {[get_property CONFIG.FREQ_HZ $endpoint] ne $hz} {
                error "Memory IP clock metadata did not resolve to its connected clock: $endpoint"
            }
        }
        return $hz
    }

    # Combine independent native masters inside one RP before its shared
    # shutdown boundary. Vendor arbitration/ID routing keeps response ownership;
    # no address or ID bit slicing is permitted at this boundary.
    proc aggregate_memory_masters {masters} {
        if {[llength $masters] == 1} {
            set master [lindex $masters 0]
            return [dict create master $master data_width [get_property CONFIG.DATA_WIDTH $master] \
                id_width [get_property CONFIG.ID_WIDTH $master]]
        }
        if {[llength $masters] < 2 || [llength $masters] > 16} {
            error "Memory RP aggregation needs between two and sixteen masters"
        }
        set merge [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect memory_merge]
        set_property -dict [list CONFIG.NUM_SI [llength $masters] CONFIG.NUM_MI 1] $merge
        connect_bd_net [get_bd_ports clk] [get_bd_pins $merge/ACLK] [get_bd_pins $merge/M00_ACLK]
        connect_bd_net [get_bd_ports rst_n] [get_bd_pins $merge/ARESETN] [get_bd_pins $merge/M00_ARESETN]
        set width 0
        set ids 0
        set i 0
        foreach master $masters {
            set slot [format S%02d $i]
            connect_bd_intf_net $master [get_bd_intf_pins $merge/${slot}_AXI]
            connect_bd_net [get_bd_ports clk] [get_bd_pins $merge/${slot}_ACLK]
            connect_bd_net [get_bd_ports rst_n] [get_bd_pins $merge/${slot}_ARESETN]
            set width [expr {max($width, [get_property CONFIG.DATA_WIDTH $master])}]
            set ids [expr {max($ids, [get_property CONFIG.ID_WIDTH $master])}]
            incr i
        }
        set source_bits 0
        while {(1 << $source_bits) < [llength $masters]} {incr source_bits}
        return [dict create master [get_bd_intf_pins $merge/M00_AXI] data_width $width \
            id_width [expr {max(1, $ids)+$source_bits}]]
    }

    # An exported IP can use its own interface names. Match by metadata and
    # normalize its memory master with the vendor converter, never bit slicing.
    proc create_rm {rm {control_base 0}} {
        set top [dict get $rm top]
        if {![dict exists $rm vlnv] || [dict get $rm vlnv] eq ""} {
            set cell [create_bd_cell -type module -reference $top $top]
            apply_rm_params $cell [dict get $rm parameters]
            connect_rm_ports $top
            return
        }
        set control_ports [get_bd_intf_ports -filter {MODE == Slave && VLNV =~ *:aximm_rtl:*}]
        set memory_ports [get_bd_intf_ports -filter {MODE == Master && VLNV =~ *:aximm_rtl:*}]
        if {[llength $control_ports] != 1 || [llength $memory_ports] != 1} {
            error "Memory RP needs one control slave and memory master boundary"
        }
        set control_port [lindex $control_ports 0]
        set memory_port [lindex $memory_ports 0]
        set control_space [get_bd_addr_spaces [get_property NAME $control_port]]
        set_property -dict [list CONFIG.PROTOCOL AXI4LITE CONFIG.ADDR_WIDTH 32 \
            CONFIG.DATA_WIDTH 32] $control_port
        set_property -dict [list CONFIG.PROTOCOL AXI4 CONFIG.ADDR_WIDTH 64 \
            CONFIG.DATA_WIDTH $::memory_data_width] $memory_port
        set_property range 0x100000000 $control_space
        set ip [create_memory_ip $rm 1]
        set name [dict get $rm cell_name]
        connect_bd_net [get_bd_ports clk] [dict get $ip clock]
        connect_bd_net [get_bd_ports rst_n] [dict get $ip reset]
        bind_memory_ip_clock $ip [get_bd_ports clk]
        set combined [aggregate_memory_masters [dict get $ip masters]]
        set master [dict get $combined master]
        set slave [dict get $ip slave]
        set native_range [dict get $ip range]
        if {$native_range > (1 << $::control_aperture_bits)} {
            error "Native control register aperture does not fit memory RP: $name"
        }
        set aperture 0
        while {(1 << $aperture) < $native_range} {incr aperture}
        # Decode only the native register aperture. Upper addresses must
        # return DECERR rather than aliasing after address-width adaptation.
        set adapter [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_crossbar control_adapter]
        # The vendor fabric has at least two slots; explicitly disable the
        # spare range (base > high), instead of aliasing register zero.
        set_property -dict [list CONFIG.PROTOCOL AXI4LITE CONFIG.NUM_SI 1 CONFIG.NUM_MI 2 \
            CONFIG.ADDR_WIDTH 32 CONFIG.M00_A00_ADDR_WIDTH $aperture \
            CONFIG.M00_A00_BASE_ADDR $control_base \
            CONFIG.M01_A00_ADDR_WIDTH 0 CONFIG.M01_A00_BASE_ADDR 0xFFFFFFFFFFFFFFFF] $adapter
        connect_bd_intf_net $control_port -boundary_type upper [get_bd_intf_pins $adapter/S00_AXI]
        connect_bd_intf_net [get_bd_intf_pins $adapter/M00_AXI] $slave
        connect_bd_net [get_bd_ports clk] [get_bd_pins $adapter/aclk]
        connect_bd_net [get_bd_ports rst_n] [get_bd_pins $adapter/aresetn]
        create_bd_addr_seg -range [expr {1 << $aperture}] -offset $control_base \
            $control_space [dict get $ip segment] control_registers
        set data_width [dict get $combined data_width]
        set id_width [dict get $combined id_width]
        if {$data_width != $::memory_data_width || $id_width != 0} {
            set converter [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dwidth_converter memory_adapter]
            set_property -dict [list CONFIG.PROTOCOL AXI4 CONFIG.ADDR_WIDTH 64 \
                CONFIG.SI_DATA_WIDTH $data_width CONFIG.MI_DATA_WIDTH $::memory_data_width \
                CONFIG.SI_ID_WIDTH [expr {max(1, $id_width)}]] $converter
            connect_bd_intf_net $master [get_bd_intf_pins $converter/S_AXI]
            connect_bd_intf_net $memory_port -boundary_type upper [get_bd_intf_pins $converter/M_AXI]
            connect_bd_net [get_bd_ports clk] [get_bd_pins $converter/s_axi_aclk]
            connect_bd_net [get_bd_ports rst_n] [get_bd_pins $converter/s_axi_aresetn]
        } else {
            connect_bd_intf_net $memory_port -boundary_type upper $master
        }
        if {[info exists ::memory_ddr_windows]} {
            map_external_memory_ddr [dict get $ip masters] $memory_port $::memory_ddr_windows
        }
    }

    # Connect an RM module's ports to the BDC boundary.
    # Connects interface ports (AXI-Stream, AXI-Lite, etc.) first,
    # then connects remaining scalar ports (clk, rst_n) while
    # skipping individual signals that belong to an interface.
    proc connect_rm_ports { rm_top } {
        set intf_port_names [list]
        foreach intf [get_bd_intf_ports] {
            set name [get_property NAME $intf]
            connect_bd_intf_net [get_bd_intf_ports $name] -boundary_type upper [get_bd_intf_pins $rm_top/$name]
            foreach sub_port [get_bd_ports ${name}_*] {
                lappend intf_port_names [get_property NAME $sub_port]
            }
        }

        foreach port [get_bd_ports] {
            set name [get_property NAME $port]
            if {[lsearch -exact $intf_port_names $name] == -1} {
                connect_bd_net [get_bd_ports $name] [get_bd_pins $rm_top/$name]
            }
        }
    }
}
