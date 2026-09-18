#!/usr/bin/env python3
"""TR-1um standard-cell Liberty characterization via ngspice.

For each logic cell in STDLIB/LogicCells/extracted:
  - takes physical area from the matching LEF SIZE W x H
  - measures effective rising/falling input charge with ngspice
  - measures 50%-to-50% propagation delay and 20/80% output transition
  - uses 5% clock-to-Q push-out searches for setup, hold, recovery, and
    removal constraints
  - sweeps 0.5/1/2/5/10/15/20 ns NLDM input transitions x output load
  - characterizes DFFR and DFFS from their own extracted electrical paths
  - preserves the extracted DFFS active-low SET polarity in the Liberty view
  - writes a Liberty file (single corner: 5V, 25C)

Usage: python3 char_liberty.py [--out liberty.lib] [--cells A,B,C]
"""
import os, sys, re, subprocess, tempfile, argparse, itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from char_utils import extract_to_spice

TR1UM = Path('/Users/yanlu/Documents/TR-1um')
EXTRACTED = TR1UM / 'STDLIB/LogicCells/extracted'
LEF_DIR = TR1UM / 'flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell/lef'
MODELS = Path(__file__).resolve().parent / 'fixed_models.sp'
NGSPICE = os.environ.get('NGSPICE', 'ngspice')

VDD = 5.0
VTH = 2.5          # 50% switching point
VLO, VHI = 0.2 * VDD, 0.8 * VDD   # 20/80% transition points
SLEW_FRACTION = (VHI - VLO) / VDD
CAP_EDGE_NS = 1.0  # effective input-charge measurement edge
PUSHOUT = 0.05     # 5% clock-to-Q delay push-out for constraints

# Cell functions (pin -> boolean expr), matching the flow Verilog models
FUNCS = {
    'INV': 'Y = !A', 'BUF': 'Y = A', 'CLKBUF': 'Y = A',
    'NAND2': 'Y = !(A * B)', 'NAND3': 'Y = !(A * B * C)', 'NAND4': 'Y = !((A * B) * (C * D))',
    'NOR2': 'Y = !(A + B)', 'NOR3': 'Y = !(A + B + C)', 'NOR4': 'Y = !((A + B) + (C + D))',
    'AND2': 'Y = (A * B)', 'AND3': 'Y = (A * B * C)', 'AND4': 'Y = ((A * B) * (C * D))',
    'OR2': 'Y = (A + B)', 'OR3': 'Y = (A + B + C)', 'OR4': 'Y = ((A + B) + (C + D))',
    'XOR2': 'Y = (A ^ B)', 'XNOR2': 'Y = !(A ^ B)',
    'MUX2': 'Y = (A * !S) + (B * S)',
    'DEL1': 'Y = A', 'DEL2': 'Y = A', 'DEL4': 'Y = A',
}
SEQ = {'DFFR', 'DFFS'}

SLEWS = [0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0]   # NLDM input transition (ns)
LOADS = [0.1, 0.5, 2.0]      # output load (pF)

SEQ_CONFIG = {
    'DFFR': {
        'control_pin': 'rst',
        'inactive_node': '0',
        'active_level': VDD,
        'inactive_level': 0.0,
        'polarity': 'P',
        'deassert_transition': 'fall',
        'assert_transition': 'rise',
    },
    'DFFS': {
        'control_pin': 'set',
        'inactive_node': 'vdd',
        'active_level': 0.0,
        'inactive_level': VDD,
        'polarity': 'N',
        'deassert_transition': 'rise',
        'assert_transition': 'fall',
    },
}


def cell_base(name):
    return re.sub(r'_X\d+$', '', name)

def seq_config(base):
    try:
        return SEQ_CONFIG[base]
    except KeyError as exc:
        raise RuntimeError(f'{base}: missing sequential-cell characterization configuration') from exc


def edge_time(slew_ns):
    """Return a source rise/fall time that produces the requested NLDM slew."""
    return max(slew_ns * 1e-9 / SLEW_FRACTION, 10e-12)


def transient_step(slew_ns):
    return max(edge_time(slew_ns) / 100.0, 10e-12)


def sequence_instance(cell_spice, base, control_node=None):
    cfg = seq_config(base)
    match = re.search(r'\.SUBCKT\s+(\S+)\s+(.*)', cell_spice)
    if not match:
        raise RuntimeError(f'{base}: cannot parse sequential subcircuit')
    subckt_name, pins = match.group(1), match.group(2).split()
    instance = []
    for pin in pins:
        lower = pin.lower()
        if lower == 'vdd':
            instance.append('vdd')
        elif lower in ('gnd', 'vss'):
            instance.append('0')
        elif lower == 'd':
            instance.append('d')
        elif lower == 'ck':
            instance.append('ck')
        elif lower == cfg['control_pin']:
            instance.append(control_node or cfg['inactive_node'])
        elif lower == 'q':
            instance.append('q')
        elif lower == 'qb':
            instance.append('qb')
        else:
            instance.append('0')
    return subckt_name, instance


def logic_inputs(base):
    return sorted({p for p in re.findall(r'\b([A-DS])\b', FUNCS[base]) if p != 'Y'})


def logic_value(base, assignment):
    expr = FUNCS[base].split('=', 1)[1].strip()
    python_expr = expr.replace('!', ' not ').replace('*', ' and ').replace('+', ' or ')
    return bool(eval(python_expr, {'__builtins__': {}}, assignment))


def sensitized_state(base, pin):
    others = [name for name in logic_inputs(base) if name != pin]
    for values in itertools.product([0, 1], repeat=len(others)):
        state = dict(zip(others, values))
        if logic_value(base, {**state, pin: 0}) != logic_value(base, {**state, pin: 1}):
            return state
    raise RuntimeError(f'{base}: cannot find a sensitized state for input {pin}')


def parse_lef_areas():
    areas = {}
    for lef in LEF_DIR.glob('*.lef'):
        text = lef.read_text()
        for match in re.finditer(r'(?ms)^MACRO\s+(\S+)\s*\n(.*?)^END\s+\1\s*$', text):
            size = re.search(r'(?m)^\s*SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)\s*;', match.group(2))
            if size:
                areas[match.group(1)] = float(size.group(1)) * float(size.group(2))
    return areas


def characterize_input_cap(cell_spice, pin, state, initial, final):
    edge = CAP_EDGE_NS * 1e-9
    t0 = 100e-9
    match = re.search(r'\.SUBCKT\s+(\S+)\s+(.*)', cell_spice, re.I)
    if not match:
        raise RuntimeError(f'cannot parse subcircuit for input-cap measurement: {pin}')
    subckt_name, pins = match.group(1), match.group(2).split()
    instance = []
    for source_pin in pins:
        lower = source_pin.lower()
        upper = source_pin.upper()
        if lower == 'vdd':
            instance.append('vdd')
        elif lower in ('gnd', 'vss'):
            instance.append('0')
        elif upper == pin.upper():
            instance.append('cap_in')
        elif lower in ('y', 'q', 'qb'):
            instance.append(lower)
        elif upper in state:
            instance.append('vdd' if state[upper] else '0')
        else:
            instance.append('0')
    net = f""".include {MODELS}
{cell_spice}
.options gmin=1e-9 reltol=1e-4
VDD vdd 0 {VDD}
VCAP cap_in 0 PULSE({initial} {final} {t0} {edge} {edge} 100n 300n)
CLY y 0 1f
CLQ q 0 1f
CLQB qb 0 1f
X1 {' '.join(instance)} {subckt_name}
.tran {edge / 20} 300n
.control
run
meas tran q_in INTEG I(VCAP) from={t0 - 0.5 * edge} to={t0 + 1.5 * edge}
print q_in
quit
.endc
.end
"""
    with tempfile.NamedTemporaryFile('w', suffix='.sp', delete=False) as fp:
        fp.write(net)
        sp_path = fp.name
    result = subprocess.run([NGSPICE, '-b', sp_path], capture_output=True, text=True)
    os.unlink(sp_path)
    match = re.search(r'(?m)^q_in\s*=\s*([-0-9.eE+]+)', result.stdout + result.stderr)
    if not match:
        raise RuntimeError(f'{subckt_name}/{pin}: SPICE input charge measurement failed')
    return abs(float(match.group(1))) / VDD * 1e12


def characterize_input_caps(cell, base, cell_spice):
    if base in SEQ:
        pins = ['CK', 'D', 'RST'] if base == 'DFFR' else ['CK', 'D', 'SET']
        defaults = {'CK': 0, 'D': 5, 'RST': 0} if base == 'DFFR' else {'CK': 0, 'D': 5, 'SET': 5}
        states = {pin: {key: value for key, value in defaults.items() if key != pin} for pin in pins}
    else:
        pins = logic_inputs(base)
        states = {pin: sensitized_state(base, pin) for pin in pins}
    caps = {}
    for pin in pins:
        rise = characterize_input_cap(cell_spice, pin, states[pin], 0, VDD)
        fall = characterize_input_cap(cell_spice, pin, states[pin], VDD, 0)
        caps[pin] = (rise, fall)
    return caps


def cap_line(pin, direction, rise, fall, indent='    '):
    average = (rise + fall) / 2.0
    lines = [
        f'{indent}pin ({pin}) {{',
        f'{indent}  direction : {direction} ;',
        f'{indent}  capacitance : {average:.6f} ;',
        f'{indent}  rise_capacitance : {rise:.6f} ;',
        f'{indent}  fall_capacitance : {fall:.6f} ;',
        f'{indent}}}',
    ]
    return lines

def sim_measure(cell_spice, inp, outp, slew_ns, load_pf, negative_unate=False, tie_high=True, period=800e-9, tie_name=None):
    """Measure a selected input arc with explicit polarity and tie state."""
    tr = edge_time(slew_ns)
    pulse = f'PULSE(0 {VDD} 20n {tr} {tr} {period/2} {period})'
    m = re.search(r'\.SUBCKT\s+(\S+)\s+(.*)', cell_spice)
    subckt_name, pins = m.group(1), m.group(2).split()
    inst = []
    for p in pins:
        pl = p.lower()
        if pl == 'vdd':
            inst.append('vdd')
        elif pl in ('gnd', 'vss'):
            inst.append('gnd')
        elif pl == inp.lower():
            inst.append(inp)
        elif pl == outp.lower():
            inst.append(outp)
        elif tie_name and pl == tie_name.lower():
            inst.append('vdd' if tie_high else '0')
        else:
            # Preserve all unselected logic inputs at a quiet rail. NAND/NOR
            # extraction pins are uppercase, but comparison is case-insensitive.
            inst.append('vdd' if tie_high else '0')
    # Ngspice already measures both transitions in absolute time. The
    # measurement pairing must follow the Boolean arc; the unused-input tie
    # level is independent of polarity.
    if negative_unate:
        tr_measure = f'meas tran tr_dly trig v({inp}) val={VTH} rise=1 targ v({outp}) val={VTH} fall=1'
        tf_measure = f'meas tran tf_dly trig v({inp}) val={VTH} fall=1 targ v({outp}) val={VTH} rise=1'
    else:
        tr_measure = f'meas tran tr_dly trig v({inp}) val={VTH} rise=1 targ v({outp}) val={VTH} rise=1'
        tf_measure = f'meas tran tf_dly trig v({inp}) val={VTH} fall=1 targ v({outp}) val={VTH} fall=1'
    net = f""".include {MODELS}
{cell_spice}
.options gmin=1e-9 reltol=1e-3
VDD vdd 0 {VDD}
VIN {inp} 0 {pulse}
CL {outp} 0 {load_pf}p
X1 {' '.join(inst)} {subckt_name}
.tran {transient_step(slew_ns)} {period}
.control
run
{tr_measure}
{tf_measure}
meas tran tr_slew trig v({outp}) val={VLO} rise=1 targ v({outp}) val={VHI} rise=1
meas tran tf_slew trig v({outp}) val={VHI} fall=1 targ v({outp}) val={VLO} fall=1
print tr_dly tf_dly tr_slew tf_slew
quit
.endc
.end
"""
    with tempfile.NamedTemporaryFile('w', suffix='.sp', delete=False) as fp:
        fp.write(net)
        sp_path = fp.name
    r = subprocess.run([NGSPICE, '-b', sp_path], capture_output=True, text=True)
    os.unlink(sp_path)
    vals = {}
    for k in re.finditer(r'(tr_dly|tf_dly|tr_slew|tf_slew)\s*=\s*([-0-9.eE+]+)', r.stdout):
        vals[k.group(1)] = float(k.group(2)) * 1e9
    return vals




def sim_measure_seq(cell_spice, base, outp, slew_ns, load_pf, data_rise, period=900e-9):
    """Measure one CK->Q transition on the cell's own electrical path."""
    tr = edge_time(slew_ns)
    data_edge = 220e-9
    subckt_name, inst = sequence_instance(cell_spice, base)
    if data_rise:
        data_pulse = f'PWL(0 0 {data_edge} 0 {data_edge + tr} {VDD} {period} {VDD})'
        delay_name = 'qdly'
        slew_name = 'qrslew'
        target_edge = 'rise=1'
        slew_measure = (
            f'meas tran {slew_name} trig v({outp}) val={VLO} rise=1 '
            f'targ v({outp}) val={VHI} rise=1'
        )
    else:
        data_pulse = f'PWL(0 {VDD} {data_edge} {VDD} {data_edge + tr} 0 {period} 0)'
        delay_name = 'qdlyf'
        slew_name = 'qfslew'
        target_edge = 'fall=1'
        slew_measure = (
            f'meas tran {slew_name} trig v({outp}) val={VHI} fall=1 '
            f'targ v({outp}) val={VLO} fall=1'
        )
    net = f""".include {MODELS}
{cell_spice}
.options gmin=1e-9 reltol=1e-3
VDD vdd 0 {VDD}
VD d 0 {data_pulse}
VCK ck 0 PULSE(0 {VDD} 20n {tr} {tr} 200n 400n)
CL {outp} 0 {load_pf}p
X1 {' '.join(inst)} {subckt_name}
.tran {transient_step(slew_ns)} {period}
.control
run
meas tran {delay_name} trig v(ck) val={VTH} rise=2 targ v({outp}) val={VTH} {target_edge}
{slew_measure}
print {delay_name} {slew_name}
quit
.endc
.end
"""
    with tempfile.NamedTemporaryFile('w', suffix='.sp', delete=False) as fp:
        fp.write(net)
        sp_path = fp.name
    r = subprocess.run([NGSPICE, '-b', sp_path], capture_output=True, text=True)
    os.unlink(sp_path)
    vals = {}
    for k in re.finditer(r'(qdly|qdlyf|qrslew|qfslew)\s*=\s*([-0-9.eE+]+)', r.stdout + r.stderr):
        vals[k.group(1)] = float(k.group(2)) * 1e9
    return vals


def sim_measure_setup_delay(cell_spice, base, data_slew_ns, clock_slew_ns, load_pf, data_rise, offset_ns):
    """Measure second-edge clock-to-Q delay for a setup push-out search."""
    data_tr = edge_time(data_slew_ns)
    clock_tr = edge_time(clock_slew_ns)
    first_edge = 20e-9
    second_edge = 200e-9
    data_mid = second_edge + 0.5 * clock_tr - offset_ns * 1e-9
    data_edge = data_mid - 0.5 * data_tr
    if data_rise:
        data_pulse = f'PWL(0 0 {data_edge} 0 {data_edge + data_tr} {VDD} 400n {VDD})'
        target_edge = 'rise=1'
    else:
        data_pulse = f'PWL(0 {VDD} {data_edge} {VDD} {data_edge + data_tr} 0 400n 0)'
        target_edge = 'fall=1'
    clock_pwl = (
        f'PWL(0 0 {first_edge} 0 {first_edge + clock_tr} {VDD} '
        f'100n {VDD} {100e-9 + clock_tr} 0 {second_edge} 0 '
        f'{second_edge + clock_tr} {VDD} 400n {VDD})'
    )
    subckt_name, instance = sequence_instance(cell_spice, base)
    net = f""".include {MODELS}
{cell_spice}
.options gmin=1e-9 reltol=1e-3
VDD vdd 0 {VDD}
VD d 0 {data_pulse}
VCK ck 0 {clock_pwl}
CL q 0 {load_pf}p
X1 {' '.join(instance)} {subckt_name}
.tran {max(min(data_tr, clock_tr) / 100.0, 10e-12)} 400n
.control
run
meas tran qdly trig v(ck) val={VTH} rise=2 targ v(q) val={VTH} {target_edge}
print qdly
quit
.endc
.end
"""
    with tempfile.NamedTemporaryFile('w', suffix='.sp', delete=False) as fp:
        fp.write(net)
        sp_path = fp.name
    r = subprocess.run([NGSPICE, '-b', sp_path], capture_output=True, text=True)
    os.unlink(sp_path)
    match = re.search(r'(?m)^qdly\s*=\s*([-0-9.eE+]+)', r.stdout + r.stderr)
    return float(match.group(1)) * 1e9 if match else None


def sim_measure_hold_delay(cell_spice, base, data_slew_ns, clock_slew_ns, load_pf, data_rise, offset_ns):
    """Measure second-edge clock-to-Q delay for a hold push-out search."""
    data_tr = edge_time(data_slew_ns)
    clock_tr = edge_time(clock_slew_ns)
    first_edge = 20e-9
    second_edge = 200e-9
    data_mid = second_edge + 0.5 * clock_tr + offset_ns * 1e-9
    data_edge = data_mid - 0.5 * data_tr
    pre_edge = 100e-9
    if data_rise:
        data_pulse = (
            f'PWL(0 {VDD} {pre_edge} {VDD} {pre_edge + data_tr} 0 '
            f'{data_edge} 0 {data_edge + data_tr} {VDD} 400n {VDD})'
        )
        target_edge = 'fall=1'
    else:
        data_pulse = (
            f'PWL(0 0 {pre_edge} 0 {pre_edge + data_tr} {VDD} '
            f'{data_edge} {VDD} {data_edge + data_tr} 0 400n 0)'
        )
        target_edge = 'rise=1'
    clock_pwl = (
        f'PWL(0 0 {first_edge} 0 {first_edge + clock_tr} {VDD} '
        f'100n {VDD} {100e-9 + clock_tr} 0 {second_edge} 0 '
        f'{second_edge + clock_tr} {VDD} 400n {VDD})'
    )
    subckt_name, instance = sequence_instance(cell_spice, base)
    net = f""".include {MODELS}
{cell_spice}
.options gmin=1e-9 reltol=1e-3
VDD vdd 0 {VDD}
VD d 0 {data_pulse}
VCK ck 0 {clock_pwl}
CL q 0 {load_pf}p
X1 {' '.join(instance)} {subckt_name}
.tran {max(min(data_tr, clock_tr) / 100.0, 10e-12)} 400n
.control
run
meas tran qdly trig v(ck) val={VTH} rise=2 targ v(q) val={VTH} {target_edge}
print qdly
quit
.endc
.end
"""
    with tempfile.NamedTemporaryFile('w', suffix='.sp', delete=False) as fp:
        fp.write(net)
        sp_path = fp.name
    r = subprocess.run([NGSPICE, '-b', sp_path], capture_output=True, text=True)
    os.unlink(sp_path)
    match = re.search(r'(?m)^qdly\s*=\s*([-0-9.eE+]+)', r.stdout + r.stderr)
    return float(match.group(1)) * 1e9 if match else None


def sim_measure_async_delay(cell_spice, base, control_slew_ns, clock_slew_ns, load_pf, check_kind, offset_ns):
    """Measure recovery/removal clock-to-Q behavior for an async control."""
    cfg = seq_config(base)
    control_tr = edge_time(control_slew_ns)
    clock_tr = edge_time(clock_slew_ns)
    first_edge = 20e-9
    second_edge = 200e-9
    clock_mid = second_edge + 0.5 * clock_tr
    if check_kind == 'recovery':
        deassert_start = clock_mid - offset_ns * 1e-9 - 0.5 * control_tr
        assert_start = None
    elif check_kind == 'removal':
        deassert_start = 100e-9
        assert_start = clock_mid + offset_ns * 1e-9 - 0.5 * control_tr
    else:
        raise ValueError(f'unknown async timing check: {check_kind}')
    points = [
        (0.0, cfg['active_level']),
        (deassert_start, cfg['active_level']),
        (deassert_start + control_tr, cfg['inactive_level']),
    ]
    if assert_start is None:
        points.append((400e-9, cfg['inactive_level']))
    else:
        points.extend([
            (assert_start, cfg['inactive_level']),
            (assert_start + control_tr, cfg['active_level']),
            (400e-9, cfg['active_level']),
        ])
    control_pwl = 'PWL(' + ' '.join(f'{time:g} {level:g}' for time, level in points) + ')'
    clock_pwl = (
        f'PWL(0 0 {first_edge} 0 {first_edge + clock_tr} {VDD} '
        f'100n {VDD} {100e-9 + clock_tr} 0 {second_edge} 0 '
        f'{second_edge + clock_tr} {VDD} 400n {VDD})'
    )
    subckt_name, instance = sequence_instance(cell_spice, base, control_node='ctrl')
    target_edge = 'rise=1' if base == 'DFFR' else 'fall=1'
    data_level = VDD if base == 'DFFR' else 0.0
    net = f""".include {MODELS}
{cell_spice}
.options gmin=1e-9 reltol=1e-3
VDD vdd 0 {VDD}
VD d 0 {data_level}
VCTRL ctrl 0 {control_pwl}
VCK ck 0 {clock_pwl}
CL q 0 {load_pf}p
X1 {' '.join(instance)} {subckt_name}
.tran {max(min(control_tr, clock_tr) / 100.0, 10e-12)} 400n
.control
run
meas tran qdly trig v(ck) val={VTH} rise=2 targ v(q) val={VTH} {target_edge}
print qdly
quit
.endc
.end
"""
    with tempfile.NamedTemporaryFile('w', suffix='.sp', delete=False) as fp:
        fp.write(net)
        sp_path = fp.name
    r = subprocess.run([NGSPICE, '-b', sp_path], capture_output=True, text=True)
    os.unlink(sp_path)
    match = re.search(r'(?m)^qdly\s*=\s*([-0-9.eE+]+)', r.stdout + r.stderr)
    return float(match.group(1)) * 1e9 if match else None


def find_pushout(measure_fn, cell_spice, base, constrained_slew_ns, related_slew_ns, load_pf, mode):
    """Find a 5% delay push-out threshold shared by sequential checks."""
    def measure(offset_ns):
        return measure_fn(
            cell_spice,
            base,
            constrained_slew_ns,
            related_slew_ns,
            load_pf,
            mode,
            offset_ns,
        )

    baseline = measure(25.0)
    if baseline is None:
        raise RuntimeError(f'{base}: {measure_fn.__name__} baseline did not produce a Q transition')
    limit = baseline * (1.0 + PUSHOUT)
    good = 25.0
    bad = 0.1
    bad_delay = measure(bad)
    if bad_delay is not None and bad_delay < limit:
        return 0.0
    for _ in range(8):
        candidate = (good + bad) / 2.0
        measured = measure(candidate)
        if measured is None or measured >= limit:
            bad = candidate
        else:
            good = candidate
    return round((good + bad) / 2.0, 4)


def characterize_constraint_tables(cell_spice, base, measure_fn, load_pf):
    rise_table = []
    fall_table = []
    for constrained_slew in SLEWS:
        rise_row = []
        fall_row = []
        for related_slew in SLEWS:
            rise_row.append(find_pushout(
                measure_fn, cell_spice, base, constrained_slew, related_slew, load_pf, True
            ))
            fall_row.append(find_pushout(
                measure_fn, cell_spice, base, constrained_slew, related_slew, load_pf, False
            ))
        rise_table.append('"' + ', '.join(f'{value:.4f}' for value in rise_row) + '"')
        fall_table.append('"' + ', '.join(f'{value:.4f}' for value in fall_row) + '"')
    return rise_table, fall_table


def characterize_setup_tables(cell_spice, base):
    return characterize_constraint_tables(cell_spice, base, sim_measure_setup_delay, 0.5)


def characterize_hold_tables(cell_spice, base):
    return characterize_constraint_tables(cell_spice, base, sim_measure_hold_delay, 0.5)


def characterize_async_table(cell_spice, base, check_kind):
    table = []
    for control_slew in SLEWS:
        row = []
        for clock_slew in SLEWS:
            row.append(find_pushout(
                sim_measure_async_delay,
                cell_spice,
                base,
                control_slew,
                clock_slew,
                0.5,
                check_kind,
            ))
        table.append('"' + ', '.join(f'{value:.4f}' for value in row) + '"')
    return table

def constraint_arc(timing_type, rise_table, fall_table):
    return [
        '      timing () {',
        '        related_pin : "CK" ;',
        f'        timing_type : {timing_type} ;',
        '        rise_constraint (constraint_template) {',
        f'          values ({", ".join(rise_table)});',
        '        }',
        '        fall_constraint (constraint_template) {',
        f'          values ({", ".join(fall_table)});',
        '        }',
        '      }',
    ]




def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(TR1UM / 'flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell/lib/TR-1um_stdcell_typ_5p0V_25C.lib'))
    ap.add_argument('--cells', default=None)
    args = ap.parse_args()

    cells = []
    for f in sorted(EXTRACTED.glob('*.extracted')):
        name = f.name[:-10]
        if name in ('TOP', 'RS', 'RR$1'):
            continue
        if args.cells and name not in args.cells.split(','):
            continue
        cells.append(name)
    areas = parse_lef_areas()
    missing_areas = sorted(set(cells) - set(areas))
    if missing_areas:
        raise RuntimeError(f'missing LEF SIZE metadata for: {missing_areas}')


    lib_dir = Path(args.out).parent
    lib_dir.mkdir(parents=True, exist_ok=True)
    slew_index = ', '.join(f'{value:.1f}' for value in SLEWS)
    load_index = ', '.join(f'{value:.1f}' for value in LOADS)

    out = []
    out += [
        'library (TR-1um_stdcell_typ_5p0V_25C) {',
        '  technology (cmos) ;',
        '  delay_model : table_lookup ;',
        '  time_unit : "1ns" ;',
        '  voltage_unit : "1V" ;',
        '  capacitive_load_unit (1, pf) ;',
        '  leakage_power_unit : "1nW" ;',
        '  nom_process : 1 ;',
        '  nom_temperature : 25 ;',
        '  nom_voltage : 5.0 ;',
        '  operating_conditions (typ) { process : 1 ; temperature : 25 ; voltage : 5.0 ; }',
        '  default_fanout_load : 1.0 ;',
        '  default_inout_pin_cap : 0.05 ;',
        '  default_input_pin_cap : 0.05 ;',
        '  default_output_pin_cap : 0.05 ;',
        '  default_max_transition : 20.0 ;',
        '  default_max_fanout : 10.0 ;',
        '  slew_lower_threshold_pct_fall : 20.0 ;',
        '  slew_upper_threshold_pct_fall : 80.0 ;',
        '  slew_lower_threshold_pct_rise : 20.0 ;',
        '  slew_upper_threshold_pct_rise : 80.0 ;',
        '  input_threshold_pct_fall : 50.0 ;',
        '  input_threshold_pct_rise : 50.0 ;',
        '  output_threshold_pct_fall : 50.0 ;',
        '  output_threshold_pct_rise : 50.0 ;',
        '  lu_table_template (delay_template) {',
        '    variable_1 : input_net_transition ;',
        '    variable_2 : total_output_net_capacitance ;',
        f'    index_1 ("{slew_index}");',
        f'    index_2 ("{load_index}");',
        '  }',
        '  lu_table_template (constraint_template) {',
        '    variable_1 : constrained_pin_transition ;',
        '    variable_2 : related_pin_transition ;',
        f'    index_1 ("{slew_index}");',
        f'    index_2 ("{slew_index}");',
        '  }',
    ]


    failures = []

    for cell in cells:
        base = cell_base(cell)
        if base in SEQ:
            print(f'CHAR {cell} (seq) ...', end=' ', flush=True)
            spi = extract_to_spice(str(EXTRACTED / (cell + '.extracted')))
            cap_by_pin = characterize_input_caps(cell, base, spi)
            setup_rise_tbl, setup_fall_tbl = characterize_setup_tables(spi, base)
            hold_rise_tbl, hold_fall_tbl = characterize_hold_tables(spi, base)
            recovery_tbl = characterize_async_table(spi, base, 'recovery')
            removal_tbl = characterize_async_table(spi, base, 'removal')
            outpin = 'q'
            rise_tbl, fall_tbl = [], []
            rtrans_tbl, ftrans_tbl = [], []
            ok = True
            for slew in SLEWS:
                r_row, f_row = [], []
                rs_row, fs_row = [], []
                for load in LOADS:
                    values = sim_measure_seq(spi, base, outpin, slew, load, True)
                    if any(key not in values for key in ('qdly', 'qrslew')):
                        ok = False
                        break
                    r_row.append(f'{values["qdly"]:.4f}')
                    rs_row.append(f'{max(values["qrslew"], 0.001):.4f}')
                if not ok:
                    break
                for load in LOADS:
                    values = sim_measure_seq(spi, base, outpin, slew, load, False)
                    if any(key not in values for key in ('qdlyf', 'qfslew')):
                        ok = False
                        break
                    f_row.append(f'{values["qdlyf"]:.4f}')
                    fs_row.append(f'{max(values["qfslew"], 0.001):.4f}')
                if not ok:
                    break
                rise_tbl.append('"' + ', '.join(r_row) + '"')
                fall_tbl.append('"' + ', '.join(f_row) + '"')
                rtrans_tbl.append('"' + ', '.join(rs_row) + '"')
                ftrans_tbl.append('"' + ', '.join(fs_row) + '"')
            if not ok:
                failures.append(cell)
                print('FAILED')
                continue
            ck_rise, ck_fall = cap_by_pin['CK']
            d_rise, d_fall = cap_by_pin['D']
            control = 'RST' if base == 'DFFR' else 'SET'
            c_rise, c_fall = cap_by_pin[control]
            cfg = seq_config(base)
            zero_table = [
                '"' + ', '.join('0.0000' for _ in SLEWS) + '"'
                for _ in SLEWS
            ]
            if cfg['deassert_transition'] == 'rise':
                recovery_rise_tbl, recovery_fall_tbl = recovery_tbl, zero_table
            else:
                recovery_rise_tbl, recovery_fall_tbl = zero_table, recovery_tbl
            if cfg['assert_transition'] == 'rise':
                removal_rise_tbl, removal_fall_tbl = removal_tbl, zero_table
            else:
                removal_rise_tbl, removal_fall_tbl = zero_table, removal_tbl
            out += [
                f'  cell ({cell}) {{',
                f'    area : {areas[cell]:.6f} ;',
                '    cell_leakage_power : 1 ;',
                '    pg_pin (VDD) { voltage_name : "VDD" ; pg_type : primary_power ; }',
                '    pg_pin (GND) { voltage_name : "GND" ; pg_type : primary_ground ; }',
                '    pin (CK) {',
                '      direction : input ;',
                '      clock : true ;',
                f'      capacitance : {(ck_rise + ck_fall) / 2.0:.6f} ;',
                f'      rise_capacitance : {ck_rise:.6f} ;',
                f'      fall_capacitance : {ck_fall:.6f} ;',
                '    }',
                '    pin (D) {',
                '      direction : input ;',
                f'      capacitance : {(d_rise + d_fall) / 2.0:.6f} ;',
                f'      rise_capacitance : {d_rise:.6f} ;',
                f'      fall_capacitance : {d_fall:.6f} ;',
            ]
            out += constraint_arc('setup_rising', setup_rise_tbl, setup_fall_tbl)
            out += constraint_arc('hold_rising', hold_rise_tbl, hold_fall_tbl)
            out += [
                '    }',
                f'    pin ({control}) {{',
                '      direction : input ;',
                f'      capacitance : {(c_rise + c_fall) / 2.0:.6f} ;',
                f'      rise_capacitance : {c_rise:.6f} ;',
                f'      fall_capacitance : {c_fall:.6f} ;',
            ]
            out += constraint_arc('recovery_rising', recovery_rise_tbl, recovery_fall_tbl)
            out += constraint_arc('removal_rising', removal_rise_tbl, removal_fall_tbl)
            out += [
                '    }',
                '    pin (Q) {',
                '      direction : output ;',
                '      function : "IQ" ;',
                '      timing () {',
                '        related_pin : "CK" ;',
                '        timing_type : rising_edge ;',
                '        cell_rise (delay_template) {',
                f'          values ({", ".join(rise_tbl)});',
                '        }',
                '        cell_fall (delay_template) {',
                f'          values ({", ".join(fall_tbl)});',
                '        }',
                '        rise_transition (delay_template) {',
                f'          values ({", ".join(rtrans_tbl)});',
                '        }',
                '        fall_transition (delay_template) {',
                f'          values ({", ".join(ftrans_tbl)});',
                '        }',
                '      }',
                '    }',
                '    pin (QB) { direction : output ; function : "IQN" ; }',
            ]
            if base == 'DFFR':
                out.append('    ff (IQ, IQN) { clocked_on : "CK" ; next_state : "D" ; clear : "RST" ; clear_polarity : "P" ; }')
            else:
                out.append('    ff (IQ, IQN) { clocked_on : "CK" ; next_state : "D" ; preset : "SET" ; preset_polarity : "N" ; }')
            out.append('  }')
            print('OK')
            continue
        # Use the correct electrical tie state for the selected input arc.
        # Positive-unate measurements require the corresponding inactive tie.
        spi = extract_to_spice(str(EXTRACTED / (cell + '.extracted')))
        cap_by_pin = characterize_input_caps(cell, base, spi)

        # Ngspice resolves the extracted subcircuit pins case-insensitively,
        # but external lowercase nodes keep the generated bench consistent
        # with the existing characterization and measure expressions.
        inpin, outpin = 'a', 'y'
        negative_unate = ('!' in FUNCS[base] or base.startswith('NAND') or base.startswith('NOR'))
        tie_name = None
        tie_high = not (base.startswith('NOR') or base.startswith('OR') or base == 'MUX2')
        if base == 'MUX2':
            tie_name, negative_unate, tie_high = 's', False, False
        elif base in ('XOR2', 'XNOR2'):
            tie_high = False
        print(f'CHAR {cell} ...', end=' ', flush=True)
        rise_tbl, fall_tbl, rslew_tbl, fslew_tbl = [], [], [], []
        ok = True
        for slew in SLEWS:
            r_row, f_row, rs_row, fs_row = [], [], [], []
            for load in LOADS:
                vals = sim_measure(spi, inpin, outpin, slew, load, negative_unate, tie_high, tie_name=tie_name)
                if any(key not in vals for key in ('tr_dly', 'tf_dly', 'tr_slew', 'tf_slew')):
                    ok = False
                    break
                if min(vals['tr_dly'], vals['tf_dly']) < 0:
                    ok = False
                    break
                r_row.append(f'{vals["tr_dly"]:.4f}')
                f_row.append(f'{vals["tf_dly"]:.4f}')
                rs_row.append(f'{max(vals["tr_slew"], 0.001):.4f}')
                fs_row.append(f'{max(vals["tf_slew"], 0.001):.4f}')
            if not ok:
                break
            rise_tbl.append('"' + ', '.join(r_row) + '"')
            fall_tbl.append('"' + ', '.join(f_row) + '"')
            rslew_tbl.append('"' + ', '.join(rs_row) + '"')
            fslew_tbl.append('"' + ', '.join(fs_row) + '"')
        if not ok:
            failures.append(cell)
            print('FAILED')
            continue

        expr = FUNCS[base]
        inputs = logic_inputs(base)
        body_fn = expr.split('=', 1)[1].strip() if '=' in expr else expr
        out.append(f'  cell ({cell}) {{')
        out.append(f'    area : {areas[cell]:.6f} ;')
        out.append('    cell_leakage_power : 1 ;')
        for p in inputs:
            rise_cap, fall_cap = cap_by_pin[p]
            out += cap_line(p, 'input', rise_cap, fall_cap)
        out.append('    pin (Y) {')
        out.append('      direction : output ;')
        out.append(f'      function : "{body_fn}" ;')
        for p in inputs:
            sense = 'negative_unate' if negative_unate else 'positive_unate'
            out += [
                '      timing () {',
                f'        related_pin : "{p}" ;',
                f'        timing_sense : {sense} ;',
                '        cell_rise (delay_template) {',
                f'          values ({", ".join(rise_tbl)});',
                '        }',
                '        cell_fall (delay_template) {',
                f'          values ({", ".join(fall_tbl)});',
                '        }',
                '        rise_transition (delay_template) {',
                f'          values ({", ".join(rslew_tbl)});',
                '        }',
                '        fall_transition (delay_template) {',
                f'          values ({", ".join(fslew_tbl)});',
                '        }',
                '      }',
            ]
        out.append('    }')
        out.append('  }')
        print('OK')

    # Wire-tie cells (constant outputs) - minimal Liberty entries.
    out.append('  cell (TIEHI) {')
    out.append(f'    area : {areas["TIEHI"]:.6f} ;')
    out.append('    pg_pin (VDD) {')
    out.append('      voltage_name : "VDD" ;')
    out.append('      pg_type : primary_power ;')
    out.append('    }')
    out.append('    pg_pin (GND) {')
    out.append('      voltage_name : "GND" ;')
    out.append('      pg_type : primary_ground ;')
    out.append('    }')
    out.append('    pin (HI) { direction : output ; function : "1" ; capacitance : 0.05 ; }')
    out.append('  }')
    out.append('  cell (TIELO) {')
    out.append(f'    area : {areas["TIELO"]:.6f} ;')
    out.append('    pg_pin (VDD) {')
    out.append('      voltage_name : "VDD" ;')
    out.append('      pg_type : primary_power ;')
    out.append('    }')
    out.append('    pg_pin (GND) {')
    out.append('      voltage_name : "GND" ;')
    out.append('      pg_type : primary_ground ;')
    out.append('    }')
    out.append('    pin (LO) { direction : output ; function : "0" ; capacitance : 0.05 ; }')
    out.append('  }')
    out.append('}')
    Path(args.out).write_text('\n'.join(out))
    print(f'\nWrote {args.out}')
    print(f'Cells: {len(cells)}, failed: {len(failures)} {failures}')


if __name__ == '__main__':
    main()
