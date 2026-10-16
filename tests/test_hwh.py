"""Partial metadata retains vendor addresses and actual exported register maps."""
import xml.etree.ElementTree as ET

import pytest

from pynq_pr.hwh import NS, complete_registers


def fixture(tmp_path):
    repo = tmp_path/'ip'; repo.mkdir()
    component = repo/'component.xml'
    component.write_text('''<component xmlns="http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009">
<vendor>example.org</vendor><library>kernel</library><name>auxiliary</name><version>1.0</version>
<busInterfaces><busInterface><name>registers</name><slave><memoryMapRef memoryMapRef="control"/></slave></busInterface></busInterfaces>
<memoryMaps><memoryMap><name>control</name><addressBlock><name>Reg</name><range>256</range><access>read-write</access>
<register><name>CTRL</name><addressOffset>0</addressOffset><size>32</size><field><name>AP_CONTINUE</name><bitOffset>4</bitOffset><bitWidth>1</bitWidth><access>read-write</access></field></register>
<register><name>buffer_1</name><addressOffset>0x10</addressOffset><size>32</size></register>
<register><name>buffer_2</name><addressOffset>0x14</addressOffset><size>32</size></register>
<register><name>transport_fault</name><addressOffset>128</addressOffset><size>32</size><description>Actual response status</description></register>
</addressBlock></memoryMap></memoryMaps></component>''')
    # Namespace-qualified IP-XACT reference attribute, as exported by Vivado.
    tree = ET.parse(component)
    ref = tree.find('s:busInterfaces/s:busInterface/s:slave/s:memoryMapRef', NS)
    ref.set('{'+NS['s']+'}memoryMapRef', ref.attrib.pop('memoryMapRef'))
    tree.write(component)
    hwh = tmp_path/'partial.hwh'
    hwh.write_text('''<EDKSYSTEM><SYSTEMINFO NAME="compute_first_inst_0"/>
<MODULES><MODULE FULLNAME="/auxiliary" VLNV="example.org:kernel:auxiliary:1.0">
<BUSINTERFACES><BUSINTERFACE NAME="registers"/></BUSINTERFACES>
<MEMORYMAP><MEMRANGE BASEVALUE="0xB0030000" HIGHVALUE="0xB00301FF"/></MEMORYMAP>
</MODULE></MODULES></EDKSYSTEM>''')
    return hwh, component, repo


def test_fill_partial_registers_without_replacing_address_or_identity(tmp_path):
    hwh, _, repo = fixture(tmp_path)
    assert complete_registers(hwh, 'example.org:kernel:auxiliary:1.0', [repo]) == 1
    tree = ET.parse(hwh)
    assert tree.find('SYSTEMINFO').get('NAME') == 'compute_first_inst_0'
    assert tree.find('.//MEMRANGE').get('BASEVALUE') == '0xB0030000'
    registers = {r.get('NAME'):r for r in tree.findall('.//REGISTERS/REGISTER')}
    assert set(registers) == {'CTRL','buffer_1','buffer_2','transport_fault'}
    for name, offset in [('buffer_1','0x10'),('buffer_2','0x14'),('transport_fault','128')]:
        assert registers[name].find("PROPERTY[@NAME='ADDRESS_OFFSET']").get('VALUE') == offset
    field = registers['CTRL'].find('FIELDS/FIELD')
    assert field.get('NAME') == 'AP_CONTINUE'
    assert field.find("PROPERTY[@NAME='BIT_OFFSET']").get('VALUE') == '4'
    before = hwh.read_bytes()
    assert complete_registers(hwh, 'example.org:kernel:auxiliary:1.0', []) == 0
    assert hwh.read_bytes() == before


@pytest.mark.parametrize('fault', ['identity','interface','definition','duplicate','registers','base'])
def test_incomplete_or_mismatched_source_does_not_rewrite_hwh(tmp_path, fault):
    hwh, component, repo = fixture(tmp_path)
    identity = 'example.org:kernel:auxiliary:1.0'
    if fault == 'identity': identity = 'example.org:kernel:different:1.0'
    if fault == 'interface': hwh.write_text(hwh.read_text().replace('NAME="registers"','NAME="wrong"'))
    if fault == 'definition': component.unlink()
    if fault == 'duplicate':
        nested = repo/'duplicate'; nested.mkdir(); (nested/'component.xml').write_bytes(component.read_bytes())
    if fault == 'registers':
        tree = ET.parse(component); block = tree.find('s:memoryMaps/s:memoryMap/s:addressBlock',NS)
        for register in block.findall('s:register',NS): block.remove(register)
        tree.write(component)
    if fault == 'base':
        tree = ET.parse(component); block = tree.find('s:memoryMaps/s:memoryMap/s:addressBlock',NS)
        ET.SubElement(block, '{'+NS['s']+'}baseAddress').text = '0x100'
        tree.write(component)
    before = hwh.read_bytes()
    with pytest.raises(ValueError): complete_registers(hwh, identity, [repo])
    assert hwh.read_bytes() == before
