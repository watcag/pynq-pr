"""Source Tcl controls; actual vendor mutability/propagation remains separate."""
from pathlib import Path
import subprocess
import pytest
UTILS=Path(__file__).parents[1]/'pynq_pr/scripts/utils.tcl'
@pytest.mark.parametrize('frequency',['124998749','125000000','100000000'])
def test_resolved_boundary_frequency_replaces_all_native_defaults(frequency):
    script=f'source {{{UTILS}}}\nset frequency {frequency}\n'+'''
set values [dict create clock 125000000 slave 125000000 m0 125000000 m1 125000000]
proc get_property {key object} {if {$object eq "boundary"} {return $::frequency};return [dict get $::values $object]}
proc set_property {key value object} {dict set ::values $object $value}
puts [utils::bind_memory_ip_clock [dict create clock clock slave slave masters {m0 m1}] boundary]
puts [dict values $values]
'''
    r=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=True)
    assert not r.stderr
    assert r.stdout.splitlines()==[frequency,' '.join([frequency]*4)]
@pytest.mark.parametrize('frequency',['{}','0','-1','124998749.0','arbitrary'])
def test_unresolved_invalid_frequency_rejected_before_metadata_change(frequency):
    script=f'source {{{UTILS}}}\nset frequency {frequency}\n'+'''
set writes 0
proc get_property {key object} {return $::frequency}
proc set_property {args} {incr ::writes}
puts [catch {utils::bind_memory_ip_clock [dict create clock clock slave slave masters {m0 m1}] boundary}]
puts $writes
'''
    r=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=True)
    assert not r.stderr and r.stdout=='1\n0\n'
def test_immutable_vendor_metadata_is_not_silently_accepted():
    script=f'source {{{UTILS}}}\n'+'''
proc get_property {key object} {if {$object eq "boundary"} {return 124998749};return 125000000}
proc set_property {args} {}
puts [catch {utils::bind_memory_ip_clock [dict create clock clock slave slave masters {m0 m1}] boundary}]
'''
    r=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=True)
    assert not r.stderr and r.stdout=='1\n'
