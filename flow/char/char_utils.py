"""TR-1um liberty characterization via ngspice.

The IP62 SPICE subckt wrappers (`.subckt PMOS/NMOS ... .param w=w`) do not
evaluate correctly in ngspice (self-referential `.param w=w`).  The flat
`.extracted` CDL netlists work, but reference device *types* `NMOS`/`PMOS`
which must be mapped to the `.model NMOS_mst`/`PMOS_mst` for ngspice.

Three cells (CLKBUF_X4, NAND3, OR3) have a PDK extraction defect: the VDD
pin is missing from the .SUBCKT and the PMOS power node is an undefined
internal node.  These are repaired here for characterization.
"""
import re

MODEL_MAP = [
    (re.compile(r'\bNMOS\b'), 'NMOS_mst'),
    (re.compile(r'\bPMOS\b'), 'PMOS_mst'),
]

# cell -> (subckt pin fix, internal-node-to-vdd rename)
# The .extracted files escape "$" as "\$"; the node fixup must match that form.
FIXUPS = {
    'CLKBUF_X4': ('A Y vdd gnd', '\\$5'),
    'NAND3': ('A B C Y vdd gnd', '\\$7'),
    'OR3': ('A Y C B vdd gnd', '\\$9'),
}


def extract_to_spice(path):
    """Read a .extracted CDL, map device types to .model names, fix PDK defects."""
    name = path.rsplit('/', 1)[-1][:-10]
    lines = []
    for line in open(path):
        if line.lstrip().startswith('*'):
            lines.append(line)
            continue
        if name in FIXUPS and '.SUBCKT' in line:
            new_pins, _ = FIXUPS[name]
            line = re.sub(r'\.SUBCKT\s+\S+\s+.*', f'.SUBCKT {name} {new_pins}', line)
        for pat, rep in MODEL_MAP:
            line = pat.sub(rep, line)
        lines.append(line)
    text = ''.join(lines)
    if name in FIXUPS:
        _, node = FIXUPS[name]
        # rename the floating PMOS power node (e.g. "$7") to vdd; only in device
        # lines (not comments, whose "$N" tokens are device labels)
        body = []
        for line in text.splitlines():
            if line.lstrip().startswith('*'):
                body.append(line)
            else:
                body.append(line.replace(node, 'vdd'))
        text = '\n'.join(body)
    return text
