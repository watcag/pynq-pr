"""Exercise publication ordering with Tcl command doubles; no routed-image claim."""
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPTS = Path(__file__).parents[1] / 'pynq_pr/scripts'
GOOD = 'Design Timing Summary\n WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns) THS Failing Endpoints THS Total Endpoints WPWS(ns) TPWS(ns) TPWS Failing Endpoints TPWS Total Endpoints\n 0.15 0 0 42 0.02 0 0 42 0.30 0 0 4\n'


def tcl(script):
    if not shutil.which('tclsh'):
        pytest.skip('tclsh required')
    return subprocess.run(['tclsh'], input=script, text=True, capture_output=True, timeout=10)


@pytest.mark.parametrize('row', [
    '-0.1 0 0 42 0.02 0 0 42 0.3 0 0 4',
    '0.1 0 0 42 -0.02 0 0 42 0.3 0 0 4',
    '0.1 0 0 42 0.02 0 0 42 -0.3 0 0 4',
    '0.1 0 0 42 0.02 0 0 42 0.3 0 0 0',
    '0.1 0 0 42 0.02 0 0 0 0.3 0 0 4',
    '0.1 0 1 42 0.02 0 0 42 0.3 0 0 4',
    'Inf 0 0 42 0.02 0 0 42 0.3 0 0 4',
    '',
])
def test_timing_requires_nonempty_passing_setup_hold_pulse(row):
    result = tcl(f'''source {{{SCRIPTS / 'qualify_impl.tcl'}}}
if {{[catch {{qualification::timing_summary {{Design Timing Summary\n{row}\n}}}} message]}} {{puts $message; exit 1}}
''')
    assert result.returncode == 1


@pytest.mark.parametrize('failure', ['', 'timing', 'verify'])
@pytest.mark.parametrize('postroute', [0, 1])
def test_all_routes_and_checks_precede_bitstream_publication(tmp_path, failure, postroute):
    design = 'example'
    generated = tmp_path / f'{design}.gen/sources_1/bd/{design}'
    files = [generated/'hw_handoff/example.hwh']
    for cell in ('first', 'second'):
        files.append(generated/f'bd/compute_{cell}_inst_0/hw_handoff/compute_{cell}_inst_0.hwh')
    for name in ('impl_base', 'impl_compute_second'):
        directory = tmp_path/name
        files += [directory/'example_wrapper.bit']
        for cell in ('first', 'second'):
            files.append(directory/f'example_i_compute_rp_compute_{cell}_inst_0_partial.bit')
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('command fixture, not FPGA data')
    (tmp_path/'bits').mkdir()
    result = tcl(f'''
set proj_dir {{{tmp_path}}}; set script_dir {{{SCRIPTS}}}
set entry_script {{{SCRIPTS/'run_impl.tcl'}}}
set bits_dir $proj_dir/bits; set design_name example; set project_name example; set jobs 2
set reconfiguration_method pcap
set partition_configs [list [dict create partition_name compute modules [list [dict create cell_name first] [dict create cell_name second]]]]
set events {{}}; set current {{}}; set failure {{{failure}}}; set postroute {postroute}
proc get_runs {{name}} {{return $name}}
proc get_files {{args}} {{return example.bd}}
proc get_bd_cells {{args}} {{return compute/rp}}
proc current_fileset {{}} {{return sources_1}}
proc set_property {{args}} {{}}
proc make_wrapper {{args}} {{}}
proc add_files {{args}} {{}}
proc update_compile_order {{args}} {{}}
proc generate_target {{args}} {{}}
proc create_pr_configuration {{args}} {{}}
proc create_run {{args}} {{}}
proc get_property {{property object}} {{
    if {{$property eq "DIRECTORY"}} {{return $::proj_dir/$object}}
    if {{$property eq "STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED"}} {{return $::postroute}}
    return fixture
}}
proc launch_runs {{args}} {{lappend ::events [join $args]}}
proc wait_on_runs {{args}} {{}}
proc wait_on_run {{args}} {{}}
proc open_run {{run}} {{set ::current $run}}
proc close_design {{}} {{}}
proc report_timing_summary {{args}} {{
    lappend ::events "timing $::current"
    if {{$::failure eq "timing" && $::current eq "impl_compute_second"}} {{return "Design Timing Summary\n-1 0 0 42 1 0 0 42 1 0 0 4"}}
    return {{{GOOD}}}
}}
proc write_checkpoint {{args}} {{lappend ::events "checkpoint $::current"}}
proc pr_verify {{args}} {{
    lappend ::events "verify $args"
    if {{$::failure eq "verify"}} {{error {{Static implementation differs}}}}
}}
set code [catch {{source $entry_script}} message]
foreach event $events {{puts $event}}
if {{$code}} {{puts $message; exit 1}}
''')
    events = result.stdout.splitlines()
    assert events[0] == 'synth_1 -jobs 2'
    if failure:
        assert result.returncode == 1, result.stderr
        assert 'write_bitstream' not in result.stdout
        assert list((tmp_path/'bits').iterdir()) == []
    else:
        assert result.returncode == 0, result.stderr + result.stdout
        verification = next(i for i, event in enumerate(events) if event.startswith('verify '))
        assert 'timing impl_compute_second' in events[:verification]
        assert 'timing impl_base' in events[:verification]
        assert '-full_check -initial' in events[verification]
        assert 'impl_base_routed.dcp' in events[verification]
        assert 'impl_compute_second_routed.dcp' in events[verification]
        assert all('write_bitstream' not in event for event in events[:verification])
        assert sum('write_bitstream' in event for event in events[verification:]) == 2
        assert len(list((tmp_path/'bits').iterdir())) == 6
    routed = 'post_route_phys_opt_design' if postroute else 'route_design'
    assert f'impl_base -to_step {routed} -jobs 2' in events
