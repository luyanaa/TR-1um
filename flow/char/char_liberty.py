#!/usr/bin/env python3
"""TR-1um standard-cell Liberty characterization via ngspice.

For each logic cell in STDLIB/LogicCells/extracted:
  - builds a transient testbench (input pulse with configurable slew, output load)
  - measures 50%-to-50% propagation delay and 20/80% output transition
  - sweeps input transition x output load -> NLDM tables
  - writes a Liberty file (single corner: 5V, 25C)

Usage: python3 char_liberty.py [--out liberty.lib] [--cells A,B,C]
"""
import os, sys, re, subprocess, tempfile, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from char_utils import extract_to_spice

TR1UM = Path('/Users/yanlu/Documents/TR-1um')
EXTRACTED = TR1UM / 'STDLIB/LogicCells/extracted'
MODELS = Path(__file__).resolve().parent / 'fixed_models.sp'
NGSPICE = os.environ.get('NGSPICE', 'ngspice')

VDD = 5.0
VTH = 2.5          # 50% switching point
VLO, VHI = 0.2 * VDD, 0.8 * VDD   # 20/80% transition points

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

SLEWS = [0.5, 1.0, 2.0]   # input slew (ns)
LOADS = [0.1, 0.5, 2.0]   # output load (pF)


def cell_base(name):
    return re.sub(r'_X\d+$', '', name)


def sim_measure(cell_spice, inp, outp, slew_ns, load_pf, negative_unate=False, tie_high=True, period=800e-9, tie_name=None):
    """Measure a selected input arc with explicit polarity and tie state."""
    tr = max(slew_ns * 1e-9 / 20, 10e-12)
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
.tran {tr} {period}
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




def sim_measure_seq(cell_spice, outp, slew_ns, load_pf, unused_d, period=800e-9):
    """DFF CK->Q delays via a two-phase test:
    phase 1: D=1, CK rises -> Q rises (qdly)
    phase 2: D=0, CK rises -> Q falls (qdlyf)"""
    tr = max(slew_ns * 1e-9 / 20, 1e-9)   # >= 1ns edge for FF capture reliability
    m = re.search(r'\.SUBCKT\s+(\S+)\s+(.*)', cell_spice)
    subckt_name, pins = m.group(1), m.group(2).split()
    inst = []
    for p in pins:
        pl = p.lower()
        if pl == 'vdd':
            inst.append('vdd')
        elif pl in ('gnd', 'vss'):
            inst.append('gnd')
        elif pl == 'd':
            inst.append('d')
        elif pl == 'ck':
            inst.append('ck')
        elif pl == 'rst':
            inst.append('gnd')   # TR-1um DFFR reset is active-HIGH: 0 = inactive
        elif pl == 'set':
            inst.append('gnd')
        elif pl == outp.lower():
            inst.append(outp)
        elif pl == 'qb':
            inst.append('qb')    # leave the other output floating
        else:
            inst.append('vdd')
    # Proven-timing two-phase pattern: D high 5n..305n (falls well before the
    # 2nd CK edge at 420n); CK high 20n..221n, period 400n; sim to 900n.
    t_d_high = 300e-9
    t_d_per = 900e-9
    t_ck = 200e-9
    period = 900e-9
    net = f""".include {MODELS}
{cell_spice}
.options gmin=1e-9 reltol=1e-3
VDD vdd 0 {VDD}
VD d 0 PULSE(0 {VDD} 5n 0.1n 0.1n {t_d_high} {t_d_per})
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
        fp.write(net)
        sp_path = fp.name
    r = subprocess.run([NGSPICE, '-b', sp_path], capture_output=True, text=True)
    os.unlink(sp_path)
    vals = {}
    for k in re.finditer(r'(qdly|qdlyf)\s*=\s*([-0-9.eE+]+)', r.stdout):
        vals[k.group(1)] = float(k.group(2)) * 1e9
    return vals


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

    lib_dir = Path(args.out).parent
    lib_dir.mkdir(parents=True, exist_ok=True)

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
        '    index_1 ("0.5, 1.0, 2.0");',
        '    index_2 ("0.1, 0.5, 2.0");',
        '  }',
    ]

    failures = []
    for cell in cells:
        base = cell_base(cell)
        if base in SEQ:
            print(f'CHAR {cell} (seq) ...', end=' ', flush=True)
            # DFFS (set-only FF) has no controllable initial state; its timing is
            # measured from the structurally identical DFFR (set vs reset variant).
            src_cell = cell if cell == 'DFFR' else 'DFFR'
            spi = extract_to_spice(str(EXTRACTED / (src_cell + '.extracted')))
            outpin = 'q'
            rise_tbl, fall_tbl = [], []
            ok = True
            for slew in SLEWS:
                r_row, f_row = [], []
                for load in LOADS:
                    v = sim_measure_seq(spi, outpin, slew, load, 5.0)   # D=1: Q rises
                    if 'qdly' not in v:
                        ok = False
                        break
                    r_row.append(f'{v["qdly"]:.4f}')
                if not ok:
                    break
                f_row0 = []
                for load in LOADS:
                    v = sim_measure_seq(spi, outpin, slew, load, 0.0)   # D=0: Q falls
                    if 'qdlyf' not in v:
                        ok = False
                        break
                    f_row0.append(f'{v["qdlyf"]:.4f}')
                if not ok:
                    break
                rise_tbl.append('"' + ', '.join(r_row) + '"')
                fall_tbl.append('"' + ', '.join(f_row0) + '"')
            if not ok:
                failures.append(cell)
                print('FAILED')
                continue
            out += [
                f'  cell ({cell}) {{',
                '    area : 200 ;',
                '    cell_leakage_power : 1 ;',
                '    pg_pin (VDD) { voltage_name : "VDD" ; pg_type : primary_power ; }',
                '    pg_pin (GND) { voltage_name : "GND" ; pg_type : primary_ground ; }',
                '    pin (CK) { direction : input ; clock : true ; capacitance : 0.1 ; }',
                '    pin (D) { direction : input ; capacitance : 0.05 ; }',
            ]
            if base == 'DFFR':
                out.append('    pin (RST) { direction : input ; capacitance : 0.05 ; }')
            else:
                out.append('    pin (SET) { direction : input ; capacitance : 0.05 ; }')
            out += [
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
                '          values ("1.0, 1.0, 1.0", "1.0, 1.0, 1.0", "1.0, 1.0, 1.0");',
                '        }',
                '        fall_transition (delay_template) {',
                '          values ("1.0, 1.0, 1.0", "1.0, 1.0, 1.0", "1.0, 1.0, 1.0");',
                '        }',
                '      }',
                '    }',
                '    pin (QB) { direction : output ; function : "IQN" ; }',
            ]
            if base == 'DFFR':
                out.append('    ff (IQ, IQN) { clocked_on : "CK" ; next_state : "D" ; clear : "RST" ; clear_polarity : "P" ; }')
            else:
                out.append('    ff (IQ, IQN) { clocked_on : "CK" ; next_state : "D" ; preset : "SET" ; }')
            out.append('  }')
            print('OK')
            continue
        # Use the correct electrical tie state for the selected input arc. A
        # positive-unate measurement with the wrong tie state is not a timing
        spi = extract_to_spice(str(EXTRACTED / (cell + '.extracted')))
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
        # all input pins used by the function (plus S for the mux)
        inputs = sorted({p for p in re.findall(r'\b([A-DS])\b', expr) if p != 'Y'})
        body_fn = expr.split('=', 1)[1].strip() if '=' in expr else expr
        out.append(f'  cell ({cell}) {{')
        out.append('    area : 100 ;')
        out.append('    cell_leakage_power : 1 ;')
        for p in inputs:
            out += [
                f'    pin ({p}) {{',
                '      direction : input ;',
                '      capacitance : 0.05 ;',
                '      rise_capacitance : 0.05 ;',
                '      fall_capacitance : 0.05 ;',
                '    }',
            ]
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
    out.append('    area : 50 ;')
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
    out.append('    area : 50 ;')
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
