# AXI-master RPs: PS/control and the complete DDR path remain static.
# Memory masters must be idle before software requests/acknowledges shutdown.
set design_name $project_name
create_bd_design $design_name
source [file join $script_dir ps_${board_name}.tcl]
set_property -dict [list CONFIG.PSU__USE__M_AXI_GP0 0 CONFIG.PSU__USE__S_AXI_GP3 0] $ps
set count [llength $partition_names]
set gpio_width [expr {max(2, $count)}]
foreach name {gpio_decouple gpio_rp_reset gpio_shutdown} {
    create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio $name
    set_property -dict [list CONFIG.C_GPIO_WIDTH $gpio_width CONFIG.C_ALL_OUTPUTS 1] [get_bd_cells $name]
    connect_bd_net $clk_net [get_bd_pins $name/s_axi_aclk]
    connect_bd_net $resetn_net [get_bd_pins $name/s_axi_aresetn]
}
set_property CONFIG.C_DOUT_DEFAULT [format 0x%08X [expr {(1 << $count)-1}]] [get_bd_cells gpio_rp_reset]
set_property -dict [list CONFIG.C_IS_DUAL 1 CONFIG.C_GPIO2_WIDTH $count CONFIG.C_ALL_INPUTS_2 1] [get_bd_cells gpio_shutdown]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat shutdown_status
set_property CONFIG.NUM_PORTS $count [get_bd_cells shutdown_status]
connect_bd_net [get_bd_pins shutdown_status/dout] [get_bd_pins gpio_shutdown/gpio2_io_i]

foreach name {rps_axi_periph rps_interconnect} {
    create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect $name
    connect_bd_net $clk_net [get_bd_pins $name/ACLK]
    connect_bd_net $resetn_net [get_bd_pins $name/ARESETN]
}
set control_count [expr {$count+3}]
set_property CONFIG.NUM_MI $control_count [get_bd_cells rps_axi_periph]
set_property -dict [list CONFIG.NUM_SI $count CONFIG.NUM_MI 1] [get_bd_cells rps_interconnect]
connect_bd_intf_net $gp1_intf [get_bd_intf_pins rps_axi_periph/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins rps_interconnect/M00_AXI] $hp0_intf
foreach pin {S00} {
    connect_bd_net $clk_net [get_bd_pins rps_axi_periph/${pin}_ACLK]
    connect_bd_net $resetn_net [get_bd_pins rps_axi_periph/${pin}_ARESETN]
}
connect_bd_net $clk_net [get_bd_pins rps_interconnect/M00_ACLK]
connect_bd_net $resetn_net [get_bd_pins rps_interconnect/M00_ARESETN]
for {set i 0} {$i<$control_count} {incr i} {
    set slot [format M%02d $i]
    connect_bd_net $clk_net [get_bd_pins rps_axi_periph/${slot}_ACLK]
    connect_bd_net $resetn_net [get_bd_pins rps_axi_periph/${slot}_ARESETN]
}
set i $count
foreach name {gpio_decouple gpio_rp_reset gpio_shutdown} {
    connect_bd_intf_net [get_bd_intf_pins [format rps_axi_periph/M%02d_AXI $i]] [get_bd_intf_pins $name/S_AXI]
    incr i
}
set signals {}
foreach {name width} [list ARVALID 1 ARREADY 1 AWVALID 1 AWREADY 1 BVALID 1 BREADY 1 RVALID 1 RREADY 1 WVALID 1 WREADY 1 \
        AWADDR 32 ARADDR 32 WDATA 32 WSTRB 4 BRESP 2 RDATA 32 RRESP 2] {
    dict set signals $name [dict create PRESENT 1 WIDTH $width]
}
set control_params [dict create INTF [dict create AXILiteS [dict create ID 0 \
    VLNV xilinx.com:interface:aximm_rtl:1.0 MODE slave PROTOCOL AXI4LITE SIGNALS $signals]] IPI_PROP_COUNT 0]
set i 0
foreach name $partition_names {
    create_bd_cell -type hier $name
    current_bd_instance /$name
    create_bd_intf_pin -mode Slave -vlnv xilinx.com:interface:aximm_rtl:1.0 S_AXI_CONTROL
    create_bd_intf_pin -mode Master -vlnv xilinx.com:interface:aximm_rtl:1.0 M_AXI
    create_bd_pin -dir I -type clk clk
    foreach pin {rst_n rp_reset_n} {create_bd_pin -dir I -type rst $pin}
    foreach pin {decouple shutdown} {create_bd_pin -dir I $pin}
    create_bd_pin -dir O in_shutdown
    create_bd_cell -type module -reference dummy_memory dummy
    set_property -dict [list CONFIG.DATA_WIDTH $memory_data_width CONFIG.CONTROL_ADDR_WIDTH 32] [get_bd_cells dummy]
    create_bd_cell -type ip -vlnv xilinx.com:ip:dfx_decoupler decoupler
    set_property -dict [list CONFIG.ALL_PARAMS $control_params CONFIG.GUI_INTERFACE_NAME AXILiteS CONFIG.GUI_INTERFACE_REGISTER false] [get_bd_cells decoupler]
    create_bd_cell -type ip -vlnv xilinx.com:ip:dfx_axi_shutdown_manager shutdown_manager
    set_property -dict [list CONFIG.RP_IS_MASTER true CONFIG.CTRL_INTERFACE_TYPE 0 \
        CONFIG.DP_PROTOCOL AXI4MM CONFIG.DP_AXI_ADDR_WIDTH 64 CONFIG.DP_AXI_DATA_WIDTH $memory_data_width CONFIG.DP_AXI_ID_WIDTH 0] [get_bd_cells shutdown_manager]
    create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic rp_reset
    set_property -dict [list CONFIG.C_OPERATION and CONFIG.C_SIZE 1] [get_bd_cells rp_reset]
    connect_bd_intf_net [get_bd_intf_pins S_AXI_CONTROL] [get_bd_intf_pins decoupler/s_AXILiteS]
    connect_bd_intf_net [get_bd_intf_pins decoupler/rp_AXILiteS] [get_bd_intf_pins dummy/s_axi_AXILiteS]
    connect_bd_intf_net [get_bd_intf_pins dummy/m_axi] [get_bd_intf_pins shutdown_manager/S_AXI]
    connect_bd_intf_net [get_bd_intf_pins shutdown_manager/M_AXI] [get_bd_intf_pins M_AXI]
    connect_bd_net [get_bd_pins clk] [get_bd_pins dummy/clk] [get_bd_pins shutdown_manager/clk]
    connect_bd_net [get_bd_pins rst_n] [get_bd_pins shutdown_manager/resetn] [get_bd_pins rp_reset/Op1]
    connect_bd_net [get_bd_pins rp_reset_n] [get_bd_pins rp_reset/Op2]
    connect_bd_net [get_bd_pins rp_reset/Res] [get_bd_pins dummy/rst_n]
    connect_bd_net [get_bd_pins decouple] [get_bd_pins decoupler/decouple]
    connect_bd_net [get_bd_pins shutdown] [get_bd_pins shutdown_manager/request_shutdown]
    connect_bd_net [get_bd_pins shutdown_manager/in_shutdown] [get_bd_pins in_shutdown]
    current_bd_instance /
    connect_bd_intf_net [get_bd_intf_pins [format rps_axi_periph/M%02d_AXI $i]] [get_bd_intf_pins $name/S_AXI_CONTROL]
    connect_bd_intf_net [get_bd_intf_pins $name/M_AXI] [get_bd_intf_pins [format rps_interconnect/S%02d_AXI $i]]
    connect_bd_net $clk_net [get_bd_pins $name/clk] [get_bd_pins [format rps_interconnect/S%02d_ACLK $i]]
    connect_bd_net $resetn_net [get_bd_pins $name/rst_n] [get_bd_pins [format rps_interconnect/S%02d_ARESETN $i]]
    foreach {tag gpio port} {decouple gpio_decouple decouple reset gpio_rp_reset rp_reset_n shutdown gpio_shutdown shutdown} {
        create_bd_cell -type ip -vlnv xilinx.com:ip:xlslice ${tag}_${name}
        set_property -dict [list CONFIG.DIN_WIDTH $gpio_width CONFIG.DIN_FROM $i CONFIG.DIN_TO $i] [get_bd_cells ${tag}_${name}]
        connect_bd_net [get_bd_pins $gpio/gpio_io_o] [get_bd_pins ${tag}_${name}/Din]
        connect_bd_net [get_bd_pins ${tag}_${name}/Dout] [get_bd_pins $name/$port]
    }
    connect_bd_net [get_bd_pins $name/in_shutdown] [get_bd_pins shutdown_status/In$i]
    incr i
}
# A full-width AXI-Lite wire is not a 4-GiB register file. Allocate small
# RP windows after the control GPIOs, using their actual PS mappings.
set next_control 0
set control_space [get_bd_addr_spaces -of_objects $gp1_intf]
foreach name {gpio_decouple gpio_rp_reset gpio_shutdown} {
    assign_bd_address [get_bd_addr_segs $name/S_AXI/Reg]
    foreach segment [get_bd_addr_segs -addressing -of_objects [get_bd_intf_pins $name/S_AXI]] {
        set next_control [expr {max($next_control, [get_property OFFSET $segment]+[get_property RANGE $segment])}]
    }
}
set control_range [expr {1 << $control_aperture_bits}]
set next_control [expr {($next_control+$control_range-1) & -$control_range}]
foreach name $partition_names {
    create_bd_addr_seg -range $control_range -offset $next_control $control_space \
        [get_bd_addr_segs $name/dummy/s_axi_AXILiteS/reg0] ${name}_control
    incr next_control $control_range
}
assign_bd_address
validate_bd_design
save_bd_design
close_bd_design $design_name
