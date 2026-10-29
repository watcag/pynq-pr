"""Execute multi-master Tcl wiring; vendor BD validation remains separate."""
from pathlib import Path
import subprocess
import pytest

UTILS=Path(__file__).parents[1]/'pynq_pr/scripts/utils.tcl'


@pytest.mark.parametrize('widths,ids', [([64],[0]),([256,256],[1,1]),([64,128,256],[4,0,1])])
def test_every_master_clock_reset_and_response_route_is_connected(widths,ids):
    masters=[f'm{i}' for i in range(len(widths))]
    properties=' '.join(f'{name},CONFIG.DATA_WIDTH {width} {name},CONFIG.ID_WIDTH {bits}'
                        for name,width,bits in zip(masters,widths,ids))
    script=f'source {{{UTILS}}}\nset properties [dict create {properties}]\n'+'''
set calls {}
proc create_bd_cell {args} {lappend ::calls [list create {*}$args];return memory_merge}
proc set_property {args} {lappend ::calls [list property {*}$args]}
proc get_bd_ports {name} {return $name}
proc get_bd_pins {name} {return $name}
proc get_bd_intf_pins {name} {return $name}
proc connect_bd_net {args} {lappend ::calls [list net {*}$args]}
proc connect_bd_intf_net {args} {lappend ::calls [list interface {*}$args]}
proc get_property {key name} {return [dict get $::properties $name,$key]}
'''+f'set result [utils::aggregate_memory_masters {{{" ".join(masters)}}}]\n'+'''
puts [list [dict get $result master] [dict get $result data_width] [dict get $result id_width]]
foreach call $calls {puts $call}
'''
    result=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=True)
    assert not result.stderr
    lines=result.stdout.splitlines()
    if len(masters)==1:
        assert lines==[f'm0 {widths[0]} {ids[0]}']
        return
    source_bits=(len(masters)-1).bit_length()
    assert lines[0]==f'memory_merge/M00_AXI {max(widths)} {max(1,max(ids))+source_bits}'
    for i,master in enumerate(masters):
        assert f'interface {master} memory_merge/S{i:02d}_AXI' in lines
        assert f'net clk memory_merge/S{i:02d}_ACLK' in lines
        assert f'net rst_n memory_merge/S{i:02d}_ARESETN' in lines
    assert 'net clk memory_merge/ACLK memory_merge/M00_ACLK' in lines
    assert 'net rst_n memory_merge/ARESETN memory_merge/M00_ARESETN' in lines


@pytest.mark.parametrize('count',[0,17])
def test_invalid_master_count_rejected_before_vendor_creation(count):
    names=' '.join(f'm{i}' for i in range(count))
    result=subprocess.run(['tclsh'],input=f'source {{{UTILS}}}\nputs [catch {{utils::aggregate_memory_masters {{{names}}}}} message]\nputs $message\n',text=True,capture_output=True,check=True)
    assert not result.stderr
    assert result.stdout.startswith('1\nMemory RP aggregation needs')


@pytest.mark.parametrize('allow,count,fault,reject', [(0,2,'',True),(1,2,'',False),
    (1,2,'protocol',True),(1,2,'address',True),(1,0,'',True),(1,17,'',True)])
def test_metadata_checks_every_master_and_static_default_stays_strict(allow,count,fault,reject):
    names=' '.join(f'm{i}' for i in range(count))
    script=f'source {{{UTILS}}}\nset masters {{{names}}}\nset fault {{{fault}}}\n'+'''
proc create_bd_cell {args} {return device}
proc set_property {args} {}
proc get_bd_intf_pins {args} {
    if {[string match *Master* $args]} {return $::masters}
    return slave
}
proc get_bd_pins {args} {
    if {[string match *clk* $args]} {return clock}
    return reset
}
proc get_bd_addr_segs {args} {return segment}
proc get_property {key object} {
    if {$object eq "m1" && $::fault eq "protocol" && $key eq "CONFIG.PROTOCOL"} {return AXI3}
    if {$object eq "m1" && $::fault eq "address" && $key eq "CONFIG.ADDR_WIDTH"} {return 32}
    switch $key {
        CONFIG.PROTOCOL {return [expr {$object eq "slave" ? "AXI4LITE" : "AXI4"}]}
        CONFIG.ADDR_WIDTH {return [expr {$object eq "slave" ? 8 : 64}]}
        CONFIG.DATA_WIDTH {return 32}
        CONFIG.POLARITY {return ACTIVE_LOW}
        RANGE {return 256}
    }
    error "unexpected metadata property"
}
'''+f'puts [catch {{utils::create_memory_ip [dict create cell_name device vlnv vendor:library:ip:1 parameters {{}}] {allow}}} result]\n'
    result=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=True)
    assert not result.stderr
    assert result.stdout.strip()==str(int(reject))
