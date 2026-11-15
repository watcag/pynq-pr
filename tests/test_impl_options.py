"""The optional `implementation` YAML settings: validation, build_config.tcl, and the run properties
run_impl.tcl sets (Tcl command doubles, no Vivado)."""
from pathlib import Path
import shutil
import subprocess

import pytest

from pynq_pr.builder import generate_tcl_config
from pynq_pr.config import apply_defaults, validate_implementation

SCRIPTS = Path(__file__).parents[1] / 'pynq_pr/scripts'
GOOD = 'Design Timing Summary\n 0.15 0 0 42 0.02 0 0 42 0.30 0 0 4\n'


@pytest.mark.parametrize('impl', [
    None, {}, {'opt_directive': 'ExploreArea'}, {'phys_opt': False}, {'place_fit_check': True},
    {'opt_directive': 'Default', 'phys_opt': True, 'place_fit_check': False},
])
def test_valid_settings(impl):
    validate_implementation(impl)


@pytest.mark.parametrize('impl, message', [
    (['ExploreArea'], 'mapping'),
    ({'opt_directive': 'exploreArea'}, 'opt_design directive'),
    ({'opt_directive': 'RQS'}, 'opt_design directive'),
    ({'phys_opt': 'false'}, 'true or false'),
    ({'place_fit_check': 1}, 'true or false'),
    ({'place_directive': 'Explore'}, 'Unknown implementation keys'),
])
def test_invalid_settings(impl, message):
    with pytest.raises(ValueError, match=message):
        validate_implementation(impl)


def build_config(impl):
    config = {'project': 'example', 'board': 'kv260', 'reconfigurable_partitions': [
        {'partition_name': 'compute', 'modules': [{'cell_name': 'first', 'top': 'first'}]}]}
    if impl is not None:
        config['implementation'] = impl
    apply_defaults(config, Path('.'))
    tcl = generate_tcl_config(config, {'part': 'xck26-sfvc784-2LV-c'}, Path('.'), Path('proj'), Path('bits'),
                              Path('pblocks.xdc'))
    return {line.split()[1]: line.split(None, 2)[2].strip('"')
            for line in tcl.splitlines() if line.startswith('set impl_')}


def test_build_config_defaults_leave_vivado_defaults():
    assert build_config(None) == {'impl_opt_directive': '', 'impl_phys_opt': '', 'impl_place_fit_check': '0'}


def test_build_config_carries_settings():
    assert build_config({'opt_directive': 'ExploreArea', 'phys_opt': False, 'place_fit_check': True}) == {
        'impl_opt_directive': 'ExploreArea', 'impl_phys_opt': '0', 'impl_place_fit_check': '1'}


def run_impl_properties(tmp_path, settings):
    """Source run_impl.tcl against command doubles; return the STEPS.* properties set on each run."""
    if not shutil.which('tclsh'):
        pytest.skip('tclsh required')
    generated = tmp_path / 'example.gen/sources_1/bd/example'
    files = [generated/'hw_handoff/example.hwh']
    for cell in ('first', 'second'):
        files.append(generated/f'bd/compute_{cell}_inst_0/hw_handoff/compute_{cell}_inst_0.hwh')
    for name in ('impl_base', 'impl_compute_second'):
        files.append(tmp_path/name/'example_wrapper.bit')
        for cell in ('first', 'second'):
            files.append(tmp_path/name/f'example_i_compute_rp_compute_{cell}_inst_0_partial.bit')
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('command fixture, not FPGA data')
    (tmp_path/'bits').mkdir()
    script = f'''
set proj_dir {{{tmp_path}}}; set script_dir {{{SCRIPTS}}}
set bits_dir $proj_dir/bits; set design_name example; set project_name example; set jobs 2
set reconfiguration_method pcap
set partition_configs [list [dict create partition_name compute modules [list [dict create cell_name first] [dict create cell_name second]]]]
{settings}
set current {{}}
proc get_runs {{name}} {{return $name}}
proc get_files {{args}} {{return example.bd}}
proc get_bd_cells {{args}} {{return compute/rp}}
proc current_fileset {{}} {{return sources_1}}
proc set_property {{args}} {{
    if {{[string match STEPS.* [lindex $args 0]]}} {{puts "prop [lindex $args 2] [lindex $args 0] [lindex $args 1]"}}
}}
proc make_wrapper {{args}} {{}}
proc add_files {{args}} {{}}
proc update_compile_order {{args}} {{}}
proc generate_target {{args}} {{}}
proc create_pr_configuration {{args}} {{}}
proc create_run {{args}} {{}}
proc get_property {{property object}} {{
    if {{$property eq "DIRECTORY"}} {{return $::proj_dir/$object}}
    if {{$property eq "STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED"}} {{return 0}}
    return fixture
}}
proc launch_runs {{args}} {{puts "launch [join $args]"}}
proc wait_on_runs {{args}} {{}}
proc wait_on_run {{args}} {{}}
proc open_run {{run}} {{set ::current $run}}
proc close_design {{}} {{}}
proc report_timing_summary {{args}} {{return {{{GOOD}}}}}
proc write_checkpoint {{args}} {{}}
proc pr_verify {{args}} {{}}
source $script_dir/run_impl.tcl
'''
    result = subprocess.run(['tclsh'], input=script, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr + result.stdout
    lines = result.stdout.splitlines()
    first_launch = next(i for i, line in enumerate(lines) if line.startswith('launch '))
    assert all(not line.startswith('prop ') for line in lines[first_launch:]), 'set after a run was launched'
    props = {}
    for line in lines[:first_launch]:
        if line.startswith('prop '):
            _, run, name, value = line.split(' ', 3)
            props.setdefault(run, {})[name] = value
    return props


@pytest.mark.parametrize('settings', ['', 'set impl_opt_directive ""; set impl_phys_opt ""; set impl_place_fit_check 0'])
def test_unset_settings_change_no_run_property(tmp_path, settings):
    assert run_impl_properties(tmp_path, settings) == {}


def test_settings_apply_to_every_implementation_run(tmp_path):
    props = run_impl_properties(
        tmp_path, 'set impl_opt_directive ExploreArea; set impl_phys_opt 0; set impl_place_fit_check 1')
    expected = {
        'STEPS.OPT_DESIGN.ARGS.DIRECTIVE': 'ExploreArea',
        'STEPS.PHYS_OPT_DESIGN.IS_ENABLED': 'false',
        'STEPS.PLACE_DESIGN.TCL.POST': str((SCRIPTS / 'place_fit_check.tcl').resolve()),
    }
    assert props == {'impl_base': expected, 'impl_compute_second': expected}


def test_phys_opt_can_be_forced_on(tmp_path):
    props = run_impl_properties(tmp_path, 'set impl_phys_opt 1')
    assert props['impl_base'] == {'STEPS.PHYS_OPT_DESIGN.IS_ENABLED': 'true'}
