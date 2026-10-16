"""Complete Vivado partial-BD HWH register maps from exported IP-XACT.

Vivado can omit ADDRESSBLOCKS for IPs in a standalone partial BD. Preserve the
vendor HWH's addressing and hierarchy; add only its missing register description.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {'s': 'http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009'}


def complete_registers(hwh_path, vlnv, repositories):
    tree = ET.parse(hwh_path)
    modules = [m for m in tree.findall('.//MODULE') if m.get('VLNV') == vlnv]
    if not modules:
        raise ValueError('Partial HWH does not contain configured IP: ' + vlnv)
    missing = [m for m in modules if not m.findall('.//REGISTERS/REGISTER')]
    if not missing:
        return 0
    definitions = []
    for repository in repositories:
        for path in Path(repository).rglob('component.xml'):
            core = ET.parse(path).getroot()
            identity = ':'.join(core.findtext('s:'+key, default='', namespaces=NS)
                                for key in ('vendor', 'library', 'name', 'version'))
            if identity == vlnv:
                definitions.append(core)
    if len(definitions) != 1:
        raise ValueError('Need one exported IP-XACT definition for: ' + vlnv)
    core = definitions[0]
    controls = [bus for bus in core.findall('s:busInterfaces/s:busInterface', NS)
                if bus.find('s:slave/s:memoryMapRef', NS) is not None]
    if len(controls) != 1:
        raise ValueError('IP needs one slave control memory map: ' + vlnv)
    control = controls[0].findtext('s:name', namespaces=NS)
    reference = controls[0].find('s:slave/s:memoryMapRef', NS).get('{'+NS['s']+'}memoryMapRef')
    maps = [m for m in core.findall('s:memoryMaps/s:memoryMap', NS)
            if m.findtext('s:name', namespaces=NS) == reference]
    blocks = [b for m in maps for b in m.findall('s:addressBlock', NS)]
    if len(blocks) != 1 or not blocks[0].findall('s:register', NS):
        raise ValueError('IP needs one described control register block: ' + vlnv)
    block = blocks[0]
    if int(block.findtext('s:baseAddress', default='0', namespaces=NS), 0) != 0:
        raise ValueError('IP needs a zero-based control register block: ' + vlnv)

    def text(element, key, default=''):
        return element.findtext('s:'+key, default=default, namespaces=NS)

    def properties(parent, values):
        for name, value in values.items():
            ET.SubElement(parent, 'PROPERTY', NAME=name, VALUE=value)

    for module in missing:
        if not any(bus.get('NAME') == control for bus in module.findall('BUSINTERFACES/BUSINTERFACE')):
            raise ValueError('Partial HWH control interface does not match IP-XACT: ' + control)
        address_blocks = module.find('ADDRESSBLOCKS')
        if address_blocks is None:
            address_blocks = ET.SubElement(module, 'ADDRESSBLOCKS')
        output = ET.SubElement(address_blocks, 'ADDRESSBLOCK', NAME=text(block, 'name'),
            INTERFACE=control, RANGE=text(block, 'range'), USAGE='register', ACCESS=text(block, 'access'))
        registers = ET.SubElement(output, 'REGISTERS')
        for register in block.findall('s:register', NS):
            access = text(register, 'access', text(block, 'access'))
            entry = ET.SubElement(registers, 'REGISTER', NAME=text(register, 'name'))
            properties(entry, dict(ADDRESS_OFFSET=text(register, 'addressOffset'),
                SIZE=text(register, 'size'), ACCESS=access, DESCRIPTION=text(register, 'description')))
            fields = ET.SubElement(entry, 'FIELDS')
            for field in register.findall('s:field', NS):
                item = ET.SubElement(fields, 'FIELD', NAME=text(field, 'name'))
                properties(item, dict(BIT_OFFSET=text(field, 'bitOffset'), BIT_WIDTH=text(field, 'bitWidth'),
                    ACCESS=text(field, 'access', access), DESCRIPTION=text(field, 'description')))
    tree.write(hwh_path, encoding='utf-8', xml_declaration=True)
    return len(missing)
