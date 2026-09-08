#!/usr/bin/env python3
"""Characterize KoheiUchi/TR_1um_sc auxiliary cells with ngspice.

Produces a single-corner Liberty file from the supplied transistor-level
subcircuits and the TR-1um model deck. The native IP62 library is untouched.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "pdk_root/TR-1um/libs.ref/TR-1um_stdcell/aux/spice"
MODELS = ROOT / "char/fixed_models.sp"
OUT_DEFAULT = ROOT / "pdk_root/TR-1um/libs.ref/TR-1um_stdcell/lib/TR-1um_aux_stdcell_typ_5p0V_25C.lib"
VDD = 5.0
VTH = 2.5
SLEWS = [0.5, 1.0, 2.0]
LOADS = [0.1, 0.5, 2.0]

CELLS = {
    "HA1S": {"inputs": ["A", "B"], "outputs": ["S", "CO"], "functions": {"S": "A ^ B", "CO": "A * B"}, "area": 68.1 * 62.6},
    "FA1D1": {"inputs": ["A", "B", "CI"], "outputs": ["S", "CO"], "functions": {"S": "(A ^ B) ^ CI", "CO": "(A * B) + (B * CI) + (A * CI)"}, "area": 89.6 * 62.6},
}


def read_subckt(cell: str) -> tuple[str, str, list[str]]:
    text = (SRC / f"{cell}.spi").read_text()
    m = re.search(r"\.subckt\s+(\S+)\s+([^\n]+)", text, re.I)
    if not m:
        raise RuntimeError(f"missing subckt header for {cell}")
    return text, m.group(1), m.group(2).split()


def parse_measures(output: str, keys: list[str]) -> dict[str, float]:
    vals = {}
    for key in keys:
        m = re.search(rf"\b{key}\s*=\s*([-+0-9.eE]+)", output)
        if m:
            vals[key] = float(m.group(1)) * 1e9
    return vals


def run_spice(deck: str, keys: list[str]) -> dict[str, float]:
    with tempfile.NamedTemporaryFile("w", suffix=".sp", delete=False) as f:
        f.write(deck)
        path = f.name
    try:
        proc = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True)
    finally:
        Path(path).unlink(missing_ok=True)
    return parse_measures(proc.stdout + proc.stderr, keys)


def sim_comb(cell: str, inp: str, outp: str, ties: dict[str, int], slew: float, load: float) -> dict[str, float]:
    body, subckt, pins = read_subckt(cell)
    nodes = []
    for pin in pins:
        p = pin.upper()
        if p == "VDD":
            nodes.append("vdd")
        elif p in {"GND", "VSS"}:
            nodes.append("0")
        elif p == inp.upper():
            nodes.append(inp.lower())
        elif p == outp.upper():
            nodes.append(outp.lower())
        else:
            nodes.append(str(ties.get(p, 0)))
    tr = max(slew / 20.0, 0.01)
    deck = f""".include {MODELS}
{body}
.options gmin=1e-9 reltol=1e-3
VDD vdd 0 {VDD}
VIN {inp.lower()} 0 PULSE(0 {VDD} 20n {tr}n {tr}n 400n 800n)
CL {outp.lower()} 0 {load}p
X1 {' '.join(nodes)} {subckt}
.tran 0.1n 800n
.control
run
meas tran rise_dly trig v({inp.lower()}) val={VTH} rise=1 targ v({outp.lower()}) val={VTH} rise=1
meas tran fall_dly trig v({inp.lower()}) val={VTH} fall=1 targ v({outp.lower()}) val={VTH} fall=1
meas tran rise_slew trig v({outp.lower()}) val=1 rise=1 targ v({outp.lower()}) val=4 rise=1
meas tran fall_slew trig v({outp.lower()}) val=4 fall=1 targ v({outp.lower()}) val=1 fall=1
print rise_dly fall_dly rise_slew fall_slew
quit
.endc
.end
"""
    return run_spice(deck, ["rise_dly", "fall_dly", "rise_slew", "fall_slew"])


def sim_dff(slew: float, load: float) -> dict[str, float]:
    body, subckt, pins = read_subckt("DFFQU1")
    nodes = {"CK": "ck", "D": "d", "Q": "q", "VDD": "vdd", "GND": "0"}
    inst = " ".join(nodes.get(p.upper(), "0") for p in pins)
    tr = max(slew / 20.0, 0.05)
    deck = f""".include {MODELS}
{body}
.options gmin=1e-9 reltol=1e-3
VDD vdd 0 {VDD}
* D=0 at first clock edge, 1 at second, 0 at third.
VD d 0 PULSE(0 {VDD} 250n 0.1n 0.1n 400n 800n)
VCK ck 0 PULSE(0 {VDD} 20n {tr}n {tr}n 200n 400n)
CL q 0 {load}p
X1 {inst} {subckt}
.tran 0.1n 900n
.control
run
meas tran q_fall1 trig v(ck) val={VTH} rise=1 targ v(q) val={VTH} fall=1
meas tran q_rise trig v(ck) val={VTH} rise=2 targ v(q) val={VTH} rise=1
meas tran q_fall2 trig v(ck) val={VTH} rise=3 targ v(q) val={VTH} fall=2
meas tran q_rise_slew trig v(q) val=1 rise=1 targ v(q) val=4 rise=1
meas tran q_fall_slew trig v(q) val=4 fall=2 targ v(q) val=1 fall=2
print q_rise q_fall2 q_rise_slew q_fall_slew
quit
.endc
.end
"""
    return run_spice(deck, ["q_rise", "q_fall2", "q_rise_slew", "q_fall_slew"])


def table(rows: list[list[float]]) -> str:
    return "\n".join('      "' + ", ".join(f"{v:.4f}" for v in row) + '"' for row in rows)


def characterize_comb(cell: str) -> list[str]:
    spec = CELLS[cell]
    arcs = {}
    for outp in spec["outputs"]:
        for inp in spec["inputs"]:
            tables = [[], [], [], []]
            for slew in SLEWS:
                rows = [[], [], [], []]
                for load in LOADS:
                    ties = {p: 0 for p in spec["inputs"] if p != inp}
                    if outp == "CO":
                        others = [p for p in spec["inputs"] if p != inp]
                        if others:
                            ties[others[0]] = 1
                    vals = sim_comb(cell, inp, outp, ties, slew, load)
                    keys = ["rise_dly", "fall_dly", "rise_slew", "fall_slew"]
                    if not all(k in vals for k in keys):
                        raise RuntimeError(f"missing {cell} {inp}->{outp} measure: {vals}")
                    for i, key in enumerate(keys):
                        rows[i].append(vals[key])
                for i in range(4):
                    tables[i].append(rows[i])
            arcs[(inp, outp)] = tables
    lines = [f"  cell ({cell}) {{", f"    area : {spec['area']:.2f} ;", "    cell_leakage_power : 1 ;"]
    for inp in spec["inputs"]:
        lines += [f"    pin ({inp}) {{", "      direction : input ;", "      capacitance : 0.05 ;", "    }"]
    for outp in spec["outputs"]:
        lines += [f"    pin ({outp}) {{", "      direction : output ;", f"      function : \"{spec['functions'][outp]}\" ;"]
        for inp in spec["inputs"]:
            rise, fall, rslew, fslew = arcs[(inp, outp)]
            lines += ["      timing () {", f"        related_pin : \"{inp}\" ;", "        timing_sense : non_unate ;", "        cell_rise (delay_template) {", f"          values (\n{table(rise)}\n          );", "        }", "        cell_fall (delay_template) {", f"          values (\n{table(fall)}\n          );", "        }", "        rise_transition (transition_template) {", f"          values (\n{table(rslew)}\n          );", "        }", "        fall_transition (transition_template) {", f"          values (\n{table(fslew)}\n          );", "        }", "      }"]
        lines += ["    }"]
    lines += ["  }"]
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    args = ap.parse_args()
    out = [
        "library (TR-1um_aux_stdcell_typ_5p0V_25C) {",
        "  technology (cmos) ;",
        "  delay_model : table_lookup ;",
        "  time_unit : \"1ns\" ;",
        "  voltage_unit : \"1V\" ;",
        "  capacitive_load_unit (1, pf) ;",
        "  nom_process : 1 ;",
        "  nom_temperature : 25 ;",
        "  nom_voltage : 5.0 ;",
        "  operating_conditions (typ) { process : 1 ; temperature : 25 ; voltage : 5.0 ; }",
        "  default_max_transition : 20.0 ;",
        "  default_max_fanout : 10.0 ;",
        "  input_threshold_pct_rise : 50.0 ;",
        "  output_threshold_pct_rise : 50.0 ;",
        "  slew_lower_threshold_pct_rise : 20.0 ;",
        "  slew_upper_threshold_pct_rise : 80.0 ;",
        "  input_threshold_pct_fall : 50.0 ;",
        "  output_threshold_pct_fall : 50.0 ;",
        "  slew_lower_threshold_pct_fall : 20.0 ;",
        "  slew_upper_threshold_pct_fall : 80.0 ;",
        "  lu_table_template (delay_template) { variable_1 : input_net_transition ; variable_2 : total_output_net_capacitance ; index_1 (\"0.5, 1.0, 2.0\"); index_2 (\"0.1, 0.5, 2.0\"); }",
        "  lu_table_template (transition_template) { variable_1 : input_net_transition ; variable_2 : total_output_net_capacitance ; index_1 (\"0.5, 1.0, 2.0\"); index_2 (\"0.1, 0.5, 2.0\"); }",
    ]
    for cell in ("HA1S", "FA1D1"):
        print(f"CHAR {cell} ...", flush=True)
        out += characterize_comb(cell)
        print("OK", flush=True)
    rise, fall, rslew, fslew = [], [], [], []
    for slew in SLEWS:
        rr, ff, rrs, ffs = [], [], [], []
        for load in LOADS:
            vals = sim_dff(slew, load)
            if not {"q_rise", "q_fall2", "q_rise_slew", "q_fall_slew"} <= vals.keys():
                raise RuntimeError(f"missing DFFQU1 measure: {vals}")
            rr.append(vals["q_rise"]); ff.append(vals["q_fall2"])
            rrs.append(vals["q_rise_slew"]); ffs.append(vals["q_fall_slew"])
        rise.append(rr); fall.append(ff); rslew.append(rrs); fslew.append(ffs)
    out += [
        "  cell (DFFQU1) {", "    area : 4920.36 ;", "    cell_leakage_power : 1 ;",
        "    pin (CK) { direction : input ; clock : true ; capacitance : 0.05 ; }",
        "    pin (D) { direction : input ; capacitance : 0.05 ; }",
        "    pin (Q) { direction : output ; function : \"IQ\" ;", "      timing () {",
        "        related_pin : \"CK\" ; timing_type : rising_edge ;",
        "        cell_rise (delay_template) {", f"          values (\n{table(rise)}\n          );", "        }",
        "        cell_fall (delay_template) {", f"          values (\n{table(fall)}\n          );", "        }",
        "        rise_transition (transition_template) {", f"          values (\n{table(rslew)}\n          );", "        }",
        "        fall_transition (transition_template) {", f"          values (\n{table(fslew)}\n          );", "        }", "      }", "    }",
        "    ff (IQ, IQN) { clocked_on : \"CK\" ; next_state : \"D\" ; }", "  }", "}",
    ]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(out) + "\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
