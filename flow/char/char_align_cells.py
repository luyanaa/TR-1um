#!/usr/bin/env python3
"""Liberty characterization for ALIGN-generated TR-1um standard cells.

Reads the design .sp netlists (LVS-verified against the ALIGN layout) and
characterizes combinational cells (NLDM: slew x load) via ngspice using the
IP62 foundry models. Sequential DFF uses the CK->Q arc.
Usage: char_align_cells.py --src <dir with .sp> --out <lib> [--cells A,B]
"""
import os, sys, re, subprocess, tempfile, argparse
from pathlib import Path

TR1UM = Path('/Users/yanlu/Documents/TR-1um')
MODELS = Path(__file__).resolve().parent / 'fixed_models.sp'
NGSPICE = os.environ.get('NGSPICE', 'ngspice')

VDD = 5.0
VTH = 2.5
VLO, VHI = 0.2 * VDD, 0.8 * VDD
SLEWS = [0.5, 1.0, 2.0]   # ns
LOADS = [0.1, 0.5, 2.0]   # pF

FUNCS = {
    'INV': 'Y = !A', 'BUF': 'Y = A',
    'NAND2': 'Y = !(A * B)', 'NAND3': 'Y = !(A * B * C)',
    'NOR2': 'Y = !(A + B)', 'NOR3': 'Y = !(A + B + C)',
    'XOR2': 'Y = (A ^ B)',
    'TIEHI': 'Y = 1', 'TIELO': 'Y = 0',
}
SEQ = {'DFF'}

def pin_directions(sp_text):
    m = re.search(r'\.subckt\s+(\S+)\s+(.*)', sp_text, re.I)
    name, pins = m.group(1), m.group(2).split()
    return name, pins

def to_ngspice(cell_spice):
    """ALIGN netlists use M<name> device syntax; the TR-1um models are subcircuits,
    so ngspice needs X<name> instances. Convert M->XM (both cases)."""
    return re.sub(r'(?mi)^(M)(\w+)', r'X\2', cell_spice)

def sim_measure(cell_spice_raw, inp, outp, slew_ns, load_pf, tie_high=True, period=800e-9):
    cell_spice = to_ngspice(cell_spice_raw)
    tr = max(slew_ns * 1e-9 / 20, 10e-12)
    pulse = f'PULSE(0 {VDD} 20n {tr} {tr} {period/2} {period})'
    subckt_name, pins = pin_directions(cell_spice)
    inst = []
    for p in pins:
        pl = p.lower()
        if pl == 'vdd': inst.append('vdd')
        elif pl in ('gnd', 'vss'): inst.append('gnd')
        elif pl == inp.lower(): inst.append(inp)
        elif pl == outp.lower(): inst.append(outp)
        else: inst.append('vdd' if tie_high else '0')
    net = f""".include {MODELS}
{cell_spice}
.options gmin=1e-9 reltol=1e-3
VDD vdd 0 {VDD}
VIN {inp} 0 {pulse}
CL {outp} 0 {load_pf}p
X1 {' '.join(inst)} {subckt_name}
.tran {tr} {period}
.control
run
meas tran tr_dly trig v({inp}) val={VTH} rise=1 targ v({outp}) val={VTH} fall=1
meas tran tf_dly trig v({inp}) val={VTH} fall=1 targ v({outp}) val={VTH} rise=1
meas tran tr_slew trig v({outp}) val={VLO} rise=1 targ v({outp}) val={VHI} rise=1
meas tran tf_slew trig v({outp}) val={VHI} fall=1 targ v({outp}) val={VLO} fall=1
print tr_dly tf_dly tr_slew tf_slew
quit
.endc
.end
"""
    with tempfile.NamedTemporaryFile('w', suffix='.sp', delete=False) as fp:
        fp.write(net); sp_path = fp.name
    r = subprocess.run([NGSPICE, '-b', sp_path], capture_output=True, text=True)
    os.unlink(sp_path)
    vals = {}
    for k in re.finditer(r'(tr_dly|tf_dly|tr_slew|tf_slew)\s*=\s*([-0-9.eE+]+)', r.stdout):
        vals[k.group(1)] = float(k.group(2)) * 1e9
    return vals

def sim_measure_seq(cell_spice_raw, outp, slew_ns, load_pf, d_val, period=900e-9):
    cell_spice = to_ngspice(cell_spice_raw)
    tr = max(slew_ns * 1e-9 / 20, 1e-9)
    subckt_name, pins = pin_directions(cell_spice)
    inst = []
    for p in pins:
        pl = p.lower()
        if pl == 'vdd': inst.append('vdd')
        elif pl in ('gnd', 'vss'): inst.append('gnd')
        elif pl == 'd': inst.append('d')
        elif pl == 'ck': inst.append('ck')
        elif pl == outp.lower(): inst.append(outp)
        else: inst.append('gnd')
    t_d_high = 300e-9
    t_ck = 200e-9
    net = f""".include {MODELS}
{cell_spice}
.options gmin=1e-9 reltol=1e-3
VDD vdd 0 {VDD}
VD d 0 {'PULSE(0 ' + str(VDD) + ' 5n 0.1n 0.1n ' + str(t_d_high) + ' 900n)' if d_val else 'PULSE(0 ' + str(VDD) + ' 5n 0.1n 0.1n 400n 900n)'}
VCK ck 0 PULSE(0 {VDD} 20n {tr} {tr} {t_ck} {2*t_ck})
CL {outp} 0 {load_pf}p
X1 {' '.join(inst)} {subckt_name}
.tran {tr} {period}
.control
run
meas tran qdly trig v(ck) val={VTH} rise=1 targ v({outp}) val={VTH} rise=1
meas tran qdlyf trig v(ck) val={VTH} rise=2 targ v({outp}) val={VTH} fall=1
print qdly qdlyf
quit
.endc
.end
"""
    with tempfile.NamedTemporaryFile('w', suffix='.sp', delete=False) as fp:
        fp.write(net); sp_path = fp.name
    r = subprocess.run([NGSPICE, '-b', sp_path], capture_output=True, text=True)
    os.unlink(sp_path)
    vals = {}
    for k in re.finditer(r'(qdly|qdlyf)\s*=\s*([-0-9.eE+]+)', r.stdout):
        vals[k.group(1)] = float(k.group(2)) * 1e9
    return vals

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='directory with <cell>.sp netlists')
    ap.add_argument('--out', required=True)
    ap.add_argument('--cells', default=None)
    args = ap.parse_args()
    src = Path(args.src)

    names = []
    for f in sorted(src.glob('*.sp')):
        n = f.stem
        if args.cells and n not in args.cells.split(','):
            continue
        names.append(n)

    lib_dir = Path(args.out).parent
    lib_dir.mkdir(parents=True, exist_ok=True)
    out = []
    out += [
        'library (TR1um_align_stdcell_typ_5p0V_25C) {',
        '  technology (cmos) ;',
        '  delay_model : table_lookup ;',
        '  time_unit : "1ns" ;',
        '  voltage_unit : "1V" ;',
        '  capacitive_load_unit (1, pf) ;',
        '  leakage_power_unit : "1nW" ;',
        '  nom_process : 1 ; nom_temperature : 25 ; nom_voltage : 5.0 ;',
        '  operating_conditions (typ) { process : 1 ; temperature : 25 ; voltage : 5.0 ; }',
        '  default_fanout_load : 1.0 ;',
        '  default_inout_pin_cap : 0.05 ; default_input_pin_cap : 0.05 ; default_output_pin_cap : 0.05 ;',
        '  default_max_transition : 20.0 ; default_max_fanout : 10.0 ;',
        '  slew_lower_threshold_pct_fall : 20.0 ; slew_upper_threshold_pct_fall : 80.0 ;',
        '  slew_lower_threshold_pct_rise : 20.0 ; slew_upper_threshold_pct_rise : 80.0 ;',
        '  input_threshold_pct_fall : 50.0 ; input_threshold_pct_rise : 50.0 ;',
        '  output_threshold_pct_fall : 50.0 ; output_threshold_pct_rise : 50.0 ;',
        '  lu_table_template (delay_template) {',
        '    variable_1 : input_net_transition ;',
        '    variable_2 : total_output_net_capacitance ;',
        '    index_1 ("0.5, 1.0, 2.0");',
        '    index_2 ("0.1, 0.5, 2.0");',
        '  }',
    ]

    failures = []
    for name in names:
        sp_text = (src / f'{name}.sp').read_text()
        base = re.sub(r'_X\d+$', '', name.upper())
        print(f'CHAR {name} ...', end=' ', flush=True)
        if base in SEQ:
            rise_tbl, fall_tbl = [], []
            ok = True
            for slew in SLEWS:
                r_row, f_row = [], []
                for load in LOADS:
                    v = sim_measure_seq(sp_text, 'Q', slew, load, 1.0)
                    if 'qdly' not in v: ok = False; break
                    r_row.append(f'{v["qdly"]:.4f}')
                if not ok: break
                for load in LOADS:
                    v = sim_measure_seq(sp_text, 'Q', slew, load, 0.0)
                    if 'qdlyf' not in v: ok = False; break
                    f_row.append(f'{v["qdlyf"]:.4f}')
                if not ok: break
                rise_tbl.append('"' + ', '.join(r_row) + '"')
                fall_tbl.append('"' + ', '.join(f_row) + '"')
            if not ok:
                failures.append(name); print('FAILED'); continue
            out += [
                f'  cell ({name.upper()}) {{',
                '    area : 100000 ;',
                '    cell_leakage_power : 1 ;',
                '    pin (CK) { direction : input ; clock : true ; capacitance : 0.1 ; }',
                '    pin (D) { direction : input ; capacitance : 0.05 ; }',
                '    pin (Q) {',
                '      direction : output ; function : "IQ" ;',
                '      timing () { related_pin : "CK" ; timing_type : rising_edge ;',
                '        cell_rise (delay_template) {',
                f'          values ({", ".join(rise_tbl)}); }}',
                '        cell_fall (delay_template) {',
                f'          values ({", ".join(fall_tbl)}); }}',
                '      }',
                '    }',
                '    ff (IQ, IQN) { clocked_on : "CK" ; next_state : "D" ; }',
                '  }',
            ]
            print('OK'); continue

        if base not in FUNCS:
            print('SKIP'); continue
        func = FUNCS[base]
        # input pins: all except VDD/GND and output Y
        sub_name, pins = pin_directions(sp_text)
        inps = [p for p in pins if p.lower() not in ('vdd', 'gnd', 'vss', 'y')]
        outp = 'Y'
        # Unused-input tie level per gate family:
        # NAND (PMOS parallel / NMOS series): unused=1 -> its NMOS conducts
        # (series chain ready) and its PMOS is off (no fight). Both arcs OK.
        # NOR (PMOS series / NMOS parallel): unused=0 -> its PMOS conducts
        # (series chain ready) and its NMOS is off (no fight). Both arcs OK.
        # XOR/INV/BUF: tie high (XOR(A,1)=!A toggles).
        tie_high = 'NOR' not in base
        if not inps and base in ('TIEHI', 'TIELO'):
            # Constant-output cells: emit the cell with a single constant-output
            # pin and no timing arcs (synthesis treats it as a tie cell).
            out += [
                f'  cell ({name.upper()}) {{',
                '    area : 50000 ;',
                '    cell_leakage_power : 1 ;',
                '    pin (Y) { direction : output ; function : "' + ('1' if base == 'TIEHI' else '0') + '" ; capacitance : 0.05 ; }',
                '  }',
            ]
            print('OK (tie)'); continue
        if not inps:
            print('SKIP (no inputs)'); continue
        rise_tbl, fall_tbl = [], []
        rslew_tbl, fslew_tbl = [], []
        ok = True
        for slew in SLEWS:
            r_row, f_row, rs_row, fs_row = [], [], [], []
            for load in LOADS:
                v = sim_measure(sp_text, inps[0], outp, slew, load, tie_high)
                if 'tr_dly' not in v: ok = False; break
                r_row.append(f'{max(v["tr_dly"],0.001):.4f}')
                rs_row.append(f'{max(v.get("tr_slew",0.001),0.001):.4f}')
            if not ok: break
            for load in LOADS:
                v = sim_measure(sp_text, inps[0], outp, slew, load, tie_high)
                if 'tf_dly' not in v: ok = False; break
                f_row.append(f'{max(v["tf_dly"],0.001):.4f}')
                fs_row.append(f'{max(v.get("tf_slew",0.001),0.001):.4f}')
            if not ok: break
            rise_tbl.append('"' + ', '.join(r_row) + '"')
            fall_tbl.append('"' + ', '.join(f_row) + '"')
            rslew_tbl.append('"' + ', '.join(rs_row) + '"')
            fslew_tbl.append('"' + ', '.join(fs_row) + '"')
        if not ok:
            failures.append(name); print('FAILED'); continue
        out += [
            f'  cell ({name.upper()}) {{',
            '    area : 100000 ;',
            '    cell_leakage_power : 1 ;',
        ]
        for p in inps:
            out.append(f'    pin ({p.upper()}) {{ direction : input ; capacitance : 0.05 ; }}')
        out.append(f'    pin ({outp}) {{ direction : output ; max_capacitance : 10.0 ; }}')
        out += [
            f'    pin ({outp}) {{',
            '      direction : output ;',
            f'      function : "{func.split("= ")[1]}" ;',
        ]
        for p in inps:
            out += [
                '      timing () {',
                f'        related_pin : "{p.upper()}" ;',
                '        timing_sense : negative_unate ;' if '!' in func or 'NAND' in base or 'NOR' in base else '        timing_sense : positive_unate ;',
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

    out.append('}')
    Path(args.out).write_text('\n'.join(out) + '\n')
    print(f'\nWrote {args.out}')
    if failures:
        print(f'FAILED cells: {failures}')

if __name__ == '__main__':
    main()
