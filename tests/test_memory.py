"""Memory PR admission and isolation ordering, without a board dependency."""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from pynq_pr.config import apply_defaults, validate


def config(tmp_path, **options):
    source = tmp_path / 'rm.v'
    source.write_text('module rm(); endmodule\n')
    return dict(project='memory', board='kv260', sources=['rm.v'],
                reconfigurable_partitions=[dict(partition_name='compute',
                modules=[dict(cell_name='first', top='rm')])], **options)


def test_stream_default_and_memory_placeholder(tmp_path):
    for options, dummy in [({}, 'dummy.v'), ({'interface': 'memory'}, 'dummy_memory.v')]:
        cfg = config(tmp_path, **options)
        validate(cfg, tmp_path)
        apply_defaults(cfg, tmp_path)
        assert Path(cfg['sources'][-1]).name == dummy
        assert cfg['control_aperture_bits'] == 8
        assert cfg['static_modules'] == []


def test_static_modules_and_generated_tcl(tmp_path):
    from pynq_pr.builder import generate_tcl_config
    from pynq_pr.boards import load_board
    import subprocess
    cfg = config(tmp_path, interface='memory', static_modules=[dict(cell_name='auxiliary',
        vlnv='vendor:library:engine:1.0', parameters={'WIDTH': 64})])
    validate(cfg, tmp_path)
    apply_defaults(cfg, tmp_path)
    text = generate_tcl_config(cfg, load_board('kv260'), tmp_path, tmp_path/'project',
        tmp_path/'bits', tmp_path/'pblocks.xdc')
    result = subprocess.run(['tclsh'], input=text + '\nputs $static_modules\n',
        text=True, capture_output=True, check=True)
    assert not result.stderr
    assert result.stdout.strip() == '{cell_name auxiliary vlnv vendor:library:engine:1.0 parameters {WIDTH 64}}'


@pytest.mark.parametrize('static', [None, {}, [{'cell_name':'auxiliary'}],
    [{'cell_name':'auxiliary','top':'rm','vlnv':'v:l:k:1'}],
    [{'cell_name':'compute','vlnv':'v:l:k:1'}],
    [{'cell_name':'gpio_shutdown','vlnv':'v:l:k:1'}],
    [{'cell_name':'reset_compute','vlnv':'v:l:k:1'}],
    [{'cell_name':'auxiliary/engine','vlnv':'v:l:k:1'}],
    [{'cell_name':'auxiliary','vlnv':'v:l:k:1','parameters':[]}],
    [{'cell_name':'auxiliary','vlnv':'v:l:k:1'}]*2,
    [{'cell_name':f'aux{i}','vlnv':'v:l:k:1'} for i in range(13)]])
def test_static_module_admission(tmp_path, static):
    with pytest.raises(ValueError):
        validate(config(tmp_path, interface='memory', static_modules=static), tmp_path)


def test_static_module_rejects_stream_interface(tmp_path):
    with pytest.raises(ValueError, match='interface: memory'):
        validate(config(tmp_path, static_modules=[dict(cell_name='auxiliary', vlnv='v:l:k:1')]), tmp_path)


def test_fixed_ip_boundary_constraints_only_when_configured(tmp_path, monkeypatch):
    import yaml
    from pynq_pr.builder import build
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('pynq_pr.builder.subprocess.run', lambda *args, **kwargs: None)
    for name, static in [('legacy', []), ('fixed', [dict(cell_name='auxiliary', vlnv='v:l:k:1')])]:
        cfg = config(tmp_path, interface='memory', static_modules=static)
        cfg['project'] = name
        path = tmp_path/(name+'.yaml')
        path.write_text(yaml.safe_dump(cfg))
        build(path, validate_only=True)
        xdc = (tmp_path/'output'/name/'pblocks.xdc').read_text()
        assert ('set_property DONT_TOUCH true [get_cells [list fixed_i/auxiliary]]' in xdc) == bool(static)
        if not static:
            assert 'DONT_TOUCH' not in xdc


@pytest.mark.parametrize('fault', ['', 'protocol', 'address', 'control', 'reset', 'masters', 'aperture'])
def test_memory_ip_metadata_admission(fault):
    """Execute the shared Tcl admission helper against unsupported interfaces."""
    import subprocess
    source = Path(__file__).parents[1]/'pynq_pr/scripts/utils.tcl'
    script = '''
set properties [dict create master,CONFIG.PROTOCOL AXI4 master,CONFIG.ADDR_WIDTH 64 \
    slave,CONFIG.PROTOCOL AXI4LITE slave,CONFIG.DATA_WIDTH 32 slave,CONFIG.ADDR_WIDTH 8 \
    reset,CONFIG.POLARITY ACTIVE_LOW segment,RANGE 256]
proc create_bd_cell {args} {return auxiliary}
proc set_property {args} {}
proc get_bd_intf_pins {args} {
    if {[string match *Master* $args]} {
        if {$::fault eq "masters"} {return {master second_master}}
        return master
    }
    return slave
}
proc get_bd_pins {args} {
    if {[string match *clk* $args]} {return clock}
    return reset
}
proc get_bd_addr_segs {args} {return segment}
proc get_property {property object} {return [dict get $::properties $object,$property]}
switch $fault {
    protocol {dict set properties master,CONFIG.PROTOCOL AXI3}
    address {dict set properties master,CONFIG.ADDR_WIDTH 32}
    control {dict set properties slave,CONFIG.DATA_WIDTH 64}
    reset {dict set properties reset,CONFIG.POLARITY ACTIVE_HIGH}
    aperture {dict set properties segment,RANGE 0}
}
set code [catch {utils::create_memory_ip [dict create cell_name auxiliary vlnv vendor:library:ip:1 parameters {}]} result]
puts $code
if {!$code} {puts [list [dict get $result master] [dict get $result reset] [dict get $result range]]}
'''
    result = subprocess.run(['tclsh'], input=f'source {{{source}}}\nset fault {{{fault}}}\n'+script,
        text=True, capture_output=True, check=True)
    assert not result.stderr
    assert result.stdout.strip() == ('1' if fault else '0\nmaster reset 256')


@pytest.mark.parametrize('options', [dict(board='pynq-z1'), dict(reconfiguration_method='icap'),
    dict(axis_switch=True), dict(streams=2), dict(memory_data_width=96), dict(control_aperture_bits=3)])
def test_memory_rejects_unsupported_transport(tmp_path, options):
    cfg = config(tmp_path, interface='memory')
    cfg.update(options)
    with pytest.raises(ValueError):
        validate(cfg, tmp_path)


@pytest.fixture
def driver():
    pynq = types.ModuleType('pynq')
    pynq.Clocks = pynq.PL = object()
    pynq.DefaultHierarchy = type('DefaultHierarchy', (), {})
    pynq.DefaultIP = type('DefaultIP', (), {})
    pynq.Overlay = type('Overlay', (), {})
    lib = types.ModuleType('pynq.lib')
    lib.AxiGPIO = object
    path = Path(__file__).parents[1] / 'pynq_pr' / 'overlay.py'
    with patch.dict(sys.modules, {'pynq': pynq, 'pynq.lib': lib}):
        spec = importlib.util.spec_from_file_location('memory_overlay_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def partition(driver, *, acknowledge=True, release=True, fail_load=False):
    events = []
    class Channel:
        def __init__(self, name, value=0):
            self.name, self.value = name, value
        def write(self, value, mask):
            events.append((self.name, value))
            self.value = (self.value & ~mask) | value
        def read(self):
            if request.value:
                return 1 if acknowledge else 0
            return 0 if release else 1
    ol = driver.Overlay.__new__(driver.Overlay)
    ol._partitions = {'compute': 0}
    request = Channel('request')
    ol._shutdown_request = request
    ol._shutdown_status = Channel('status')
    ol._rp_reset = Channel('reset', 1)
    ol._decoupler = Channel('isolate')
    rp = driver.PrPartition.__new__(driver.PrPartition)
    rp._overlay = ol
    rp.description = {'fullpath': 'compute', 'ip': {'shutdown_manager':
        {'type': 'xilinx.com:ip:dfx_axi_shutdown_manager:1.0'}}}
    def load(bit):
        events.append(('load', bit))
        assert request.value == ol._decoupler.value == 1
        assert ol._rp_reset.value == 0
        if fail_load:
            raise OSError('load failed')
    rp.rp = types.SimpleNamespace(download=load)
    return rp, ol, events


def test_memory_swap_drains_then_isolates(driver):
    rp, ol, events = partition(driver)
    def drained():
        events.append(('caller-drained', True))
        return True
    rp.download('second.bit', drained=drained)
    assert events == [('caller-drained', True), ('isolate', 1), ('request', 1),
        ('reset', 0), ('load', 'second.bit'), ('request', 0), ('reset', 1), ('isolate', 0)]


def test_undrained_caller_cannot_start_swap(driver):
    rp, ol, events = partition(driver)
    for drained in (None, lambda: False):
        with pytest.raises(RuntimeError):
            rp.download('second.bit', drained=drained)
    assert not events


def test_shutdown_timeout_does_not_reset_outstanding_master(driver):
    rp, ol, events = partition(driver, acknowledge=False)
    with pytest.raises(RuntimeError, match="recovery uncertain") as error:
        rp.download('second.bit', drained=lambda: True, timeout=0)
    assert isinstance(error.value.__cause__, TimeoutError)
    assert events == [('isolate', 1), ('request', 1), ('isolate', 1), ('request', 1)]
    assert ol._rp_reset.value == 1


@pytest.mark.parametrize('failure', ['load', 'release'])
def test_failed_swap_keeps_reset_and_isolation(driver, failure):
    rp, ol, events = partition(driver, fail_load=failure == 'load', release=failure != 'release')
    with pytest.raises((OSError, TimeoutError)):
        rp.download('second.bit', drained=lambda: True, timeout=0)
    assert ol._shutdown_request.value == ol._decoupler.value == 1
    assert ol._rp_reset.value == 0


def test_hierarchy_recognizes_both_transports(driver):
    for ip in ('axi_dma', 'dfx_axi_shutdown_manager'):
        assert driver.PrPartition.checkhierarchy(dict(hierarchies={'rp': {}},
            ip={'transport': {'type': f'xilinx.com:ip:{ip}:1.0'}}))
    assert not driver.PrPartition.checkhierarchy(dict(hierarchies={'rp': {}}, ip={}))


def test_ip_module_config_and_tcl_generation(tmp_path):
    from pynq_pr.builder import generate_tcl_config
    from pynq_pr.boards import load_board
    import subprocess
    repo = tmp_path / 'ip'
    repo.mkdir()
    for ip_module in (False, True):
        cfg = config(tmp_path, interface='memory' if ip_module else 'stream')
        if ip_module:
            cfg['sources'] = []
            cfg['ip_repositories'] = ['ip']
            cfg['reconfigurable_partitions'][0]['modules'][0] = dict(
                cell_name='first', vlnv='vendor:library:kernel:1.0')
        validate(cfg, tmp_path)
        apply_defaults(cfg, tmp_path)
        text = generate_tcl_config(cfg, load_board('kv260'), tmp_path,
            tmp_path / 'project', tmp_path / 'bits', tmp_path / 'pblocks.xdc', jobs=2, validate_only=ip_module)
        # Actually parse generated Tcl; verify both legacy and IP records survive.
        check = '\nputs [dict get [lindex [dict get [lindex $partition_configs 0] modules] 0] '
        result = subprocess.run(['tclsh'], input=text + check + ('vlnv]' if ip_module else 'top]'),
            text=True, capture_output=True, check=True)
        assert not result.stderr
        assert result.stdout.strip() == ('vendor:library:kernel:1.0' if ip_module else 'rm')
        assert ('set rp_interface "memory"' in text) == ip_module
        assert f'set validate_only "{int(ip_module)}"' in text


def test_ip_module_rejects_ambiguous_or_stream_interfaces(tmp_path):
    cfg = config(tmp_path)
    module = cfg['reconfigurable_partitions'][0]['modules'][0]
    module['vlnv'] = 'vendor:library:kernel:1.0'
    with pytest.raises(ValueError, match='exactly one'):
        validate(cfg, tmp_path)
    del module['top']
    with pytest.raises(ValueError, match='interface: memory'):
        validate(cfg, tmp_path)


@pytest.mark.parametrize('channel_name,release_value', [('_shutdown_request', 0),
    ('_rp_reset', 1), ('_decoupler', 0)])
def test_late_gpio_failure_recovers_before_return(driver, channel_name, release_value):
    rp, ol, events = partition(driver)
    channel = getattr(ol, channel_name)
    original = channel.write
    failed = False
    def write(value, mask):
        nonlocal failed
        original(value, mask)  # Failure may occur after the write reached hardware.
        if value == release_value and not failed:
            failed = True
            raise OSError('late GPIO write failed')
    channel.write = write
    with pytest.raises(OSError, match='late GPIO'):
        rp.download('second.bit', drained=lambda: True, timeout=0)
    assert ol._shutdown_request.value == ol._decoupler.value == 1
    assert ol._rp_reset.value == 0
    assert events[-3:] == [('isolate', 1), ('request', 1), ('reset', 0)]


def test_failed_gpio_recovery_reports_uncertainty(driver):
    rp, ol, events = partition(driver)
    original = ol._decoupler.write
    def write(value, mask):
        original(value, mask)
        if any(event[0] == 'load' for event in events):
            raise OSError('GPIO is unavailable')
    ol._decoupler.write = write
    with pytest.raises(RuntimeError, match='recovery uncertain') as error:
        rp.download('second.bit', drained=lambda: True, timeout=0)
    assert isinstance(error.value.__cause__, OSError)
    assert ol._shutdown_request.value == 1
    assert ol._rp_reset.value == 0


def test_stream_simulator_cannot_claim_memory_validation(tmp_path, monkeypatch):
    from pynq_pr.sim import generate_sim_config
    import yaml
    path = tmp_path / 'memory.yaml'
    path.write_text(yaml.safe_dump(config(tmp_path, interface='memory')))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(NotImplementedError, match='AXI-master testbench'):
        generate_sim_config(path)
    assert not (tmp_path / 'sim').exists()


@pytest.mark.parametrize('channel_name', ['_decoupler', '_shutdown_request'])
def test_initial_gpio_after_effect_failure_still_isolates(driver, channel_name):
    rp, ol, events = partition(driver)
    channel = getattr(ol, channel_name)
    original = channel.write
    failed = False
    def write(value, mask):
        nonlocal failed
        original(value, mask)
        if not failed:
            failed = True
            raise OSError('initial GPIO write failed')
    channel.write = write
    with pytest.raises(OSError, match='initial GPIO'):
        rp.download('second.bit', drained=lambda: True, timeout=0)
    assert not any(event[0] == 'load' for event in events)
    assert ol._decoupler.value == ol._shutdown_request.value == 1
    assert ol._rp_reset.value == 0


def test_validate_only_cli_forwarding(monkeypatch):
    from pynq_pr.cli import main
    from unittest.mock import Mock
    run = Mock()
    monkeypatch.setattr('pynq_pr.builder.build', run)
    monkeypatch.setattr(sys, 'argv', ['pynq-pr', 'build', '-c', 'memory.yaml', '--validate-only', '-j', '2'])
    main()
    run.assert_called_once_with('memory.yaml', force=False, jobs=2, validate_only=True)
