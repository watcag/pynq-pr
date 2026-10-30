"""Execute DDR mapping Tcl; mocked metadata does not qualify vendor routing."""
from pathlib import Path
import subprocess
import pytest
UTILS=Path(__file__).parents[1]/'pynq_pr/scripts/utils.tcl'
def tcl(body):
 r=subprocess.run(['tclsh'],input=f'source {{{UTILS}}}\n'+body,text=True,capture_output=True,check=True)
 assert not r.stderr
 return r.stdout

def test_real_sized_disjoint_ddr_windows_preserve_above_32bit_addresses():
 out=tcl('set w [list [dict create segment high offset 0x800000000 range 0x800000000] [dict create segment low offset 0 range 0x80000000]]\nputs [utils::memory_window_pairs $w]\n')
 assert out.strip()=='offset 0 range 2147483648 offset 34359738368 range 34359738368'
@pytest.mark.parametrize('windows',['{}','{segment low offset {} range 4096}','{segment low offset -1 range 4096}',
 '{segment low offset 1 range 4096}','{segment low offset 0 range 0}','{segment low offset 0 range 3000}',
 '{segment low offset 0xffffffffffffffff range 2}','{segment low offset 0 range 4096} {segment duplicate offset 0 range 4096}',
 '{segment low offset 0 range 8192} {segment overlap offset 4096 range 4096}'])
def test_invalid_or_overlapping_windows_rejected(windows):
 assert tcl(f'puts [catch {{utils::checked_memory_windows {{{windows}}}}}]\n').strip()=='1'

def test_external_virtual_reg_gets_both_full_ddr_ranges_not_inferred_64k():
 script='''
set calls {}
proc get_bd_addr_segs {args} {if {[lindex $args end] eq "external"} {return Reg};return {old64K}}
proc get_bd_addr_spaces {args} {return [lindex $args end]}
proc delete_bd_objs {objects} {lappend ::calls [list delete $objects]}
proc assign_bd_address {args} {lappend ::calls [list assign {*}$args];return {low_map high_map}}
set w [list [dict create segment low offset 0 range 0x80000000] [dict create segment high offset 0x800000000 range 0x800000000]]
utils::map_external_memory_ddr {program data} external $w
foreach c $calls {puts $c}
'''
 out=tcl(script)
 for master in ['program','data']:
  assert f'-external -dict {{offset 0 range 2147483648 offset 34359738368 range 34359738368}} -target_address_space {master} Reg' in out
 assert out.count('delete old64K')==2

def test_static_route_uses_authoritative_windows_and_excludes_peripherals():
 script='''
set calls {}
proc get_bd_addr_spaces {args} {return native}
proc get_property {name object} {return 65536}
proc set_property {args} {lappend ::calls [list property {*}$args]}
proc get_bd_addr_segs {args} {return {old64K}}
proc delete_bd_objs {args} {lappend ::calls [list delete {*}$args]}
proc create_bd_addr_seg {args} {lappend ::calls [list create {*}$args]}
proc exclude_bd_addr_seg {args} {lappend ::calls [list exclude {*}$args]}
set w [list [dict create segment low offset 0 range 0x80000000] [dict create segment high offset 0x800000000 range 0x800000000]]
utils::map_memory_ddr master $w {OCM QSPI}
foreach c $calls {puts $c}
'''
 out=tcl(script)
 assert 'create -offset 0 -range 2147483648 native low ddr_0' in out
 assert 'create -offset 34359738368 -range 34359738368 native high ddr_1' in out
 assert 'exclude -target_address_space native OCM' in out
 assert 'exclude -target_address_space native QSPI' in out
 assert 'property RANGE 68719476736 native' in out

def test_external_assignment_failure_not_ignored():
 assert tcl('''
proc get_bd_addr_segs {args} {if {[lindex $args end] eq "external"} {return Reg};return {}}
proc get_bd_addr_spaces {args} {return native}
proc assign_bd_address {args} {return {}}
puts [catch {utils::map_external_memory_ddr {master} external [list [dict create segment low offset 0 range 4096]]}]
''').splitlines()[-1]=='1'


@pytest.mark.parametrize('actual,required,reject', [
 ('{segment low offset 0 range 0x80000000} {segment high offset 0x800000000 range 0x800000000}',268976128,False),
 ('{segment low offset 0x76000000 range 65536} {segment high offset 0x800000000 range 0x800000000}',268976128,True),
 ('{segment low offset 0 range 0x80000000}',268976128,True),
 ('{segment low offset 0 range 0x80000000} {segment high offset 0x800000000 range 0x800000000} {segment OCM offset 0xff000000 range 0x1000000}',268976128,True),
 ('{segment low offset 0 range 0x80000000} {segment high offset 0x800000000 range 0x800000000}',1<<40,True)])
def test_coverage_rejects_narrow_or_extra_routes_and_undersized_bo_envelope(actual,required,reject):
    script='set expected [list [dict create segment low offset 0 range 0x80000000] [dict create segment high offset 0x800000000 range 0x800000000]]\n'
    script+=f'puts [catch {{utils::require_memory_coverage $expected {{{actual}}} {required}}}]\n'
    assert tcl(script).strip()==str(int(reject))

def test_large_high_window_cannot_hide_insufficient_low_cma_aperture():
    script = '''
set windows [list [dict create segment low offset 0 range 65536] [dict create segment high offset 0x800000000 range 0x800000000]]
puts [catch {utils::require_memory_coverage $windows $windows 536870912}]
'''
    assert tcl(script).strip() == '1'

@pytest.mark.parametrize('value,valid', [('0',True),('0x800000000',True),('18446744073709551615',True),('-1',False),('1.0',False),('1e9',False),('Inf',False),('NaN',False),('1+1',False),('',False),('0x',False)])
def test_exact_integer_parser_does_not_require_newer_tcl_entier_class(value,valid):
    script = '''
rename string host_string
proc string {args} {
 if {[lindex $args 0] eq "is" && [lindex $args 1] eq "entier"} {error "Vivado Tcl lacks entier"}
 return [uplevel 1 [linsert $args 0 host_string]]
}
'''
    script += f'puts [utils::is_nonnegative_integer {{{value}}}]\n'
    assert tcl(script).strip() == str(int(valid))

def test_ddr_windows_execute_when_entier_class_is_unavailable():
    script = '''
rename string host_string
proc string {args} {
 if {[lindex $args 0] eq "is" && [lindex $args 1] eq "entier"} {error "Vivado Tcl lacks entier"}
 return [uplevel 1 [linsert $args 0 host_string]]
}
set windows [list [dict create segment low offset 0 range 2147483648] [dict create segment high offset 0x800000000 range 0x800000000]]
utils::require_memory_coverage $windows $windows 536870912
puts PASS
'''
    assert tcl(script).strip() == 'PASS'
