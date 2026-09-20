#!/usr/bin/env python3
"""Run the final TR10-1 DCDC characterization with explicit PDK provenance.

The source schematic is from the legacy OpenRule1um TR10 project.  The runner
keeps that source topology intact and evaluates it twice:

* the original OpenRule1um compact models (historical source-level reference);
* the explicit source-to-TR-1um device-name mapping used by the current
  engineering conversion (NMOS/PMOS in fixed_models.sp).

The clock is injected at the measured TR10-1 VCO frequencies so the DCDC
result is not confused with an uncalibrated VCO model prediction.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/tr10_rcx_vco/final_characterization/openrule1um_dcdc"
SOURCE_NETLIST = Path("/tmp/tr10-xschem/out-final/dcdc_down_full_tb")
OLD_MODEL_ROOT = Path("/tmp/tr10-xschem/lib/TR10")
CURRENT_MODELS = ROOT / "flow/char/fixed_models.sp"
SOURCE_SCHEMATIC = Path("/tmp/TR10-1/member_project/DCDC_DOWN/xschem/dcdc_down_full_tb.sch")

FREQUENCIES = [
    {"label": "measured_vctrl_0p5V", "vctrl_V": 0.5, "frequency_Hz": 1.652357852},
    {"label": "measured_vctrl_2p5V", "vctrl_V": 2.5, "frequency_Hz": 20170.90997},
    {"label": "measured_vctrl_5p0V", "vctrl_V": 5.0, "frequency_Hz": 33736.669},
    {"label": "xschem_external_clock", "vctrl_V": None, "frequency_Hz": 90000.0},
]
LOADS_OHM = [10.0, 1_000.0, 10_000.0, 1_000_000.0, 1_000_000_000.0]

MODEL_SETS = {
    "openrule1um_source": {
        "includes": [
            OLD_MODEL_ROOT / "mos.lib",
            OLD_MODEL_ROOT / "passive.lib",
            OLD_MODEL_ROOT / "diode.lib",
        ],
        "nmos": "nchor1ex",
        "pmos": "pchor1ex",
        "mapping": "none; retain legacy nchor1ex/pchor1ex names",
    },
    "tr1um_mapped": {
        "includes": [CURRENT_MODELS],
        "nmos": "NMOS",
        "pmos": "PMOS",
        "mapping": "nchor1ex->NMOS, pchor1ex->PMOS; geometry preserved",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def clean_xschem_netlist(text: str) -> str:
    """Remove Xschem's embedded control block and hoist model includes."""
    includes: list[str] = []
    body: list[str] = []
    in_architecture = False
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped == "**** begin user architecture code":
            in_architecture = True
            continue
        if stripped == "**** end user architecture code":
            in_architecture = False
            continue
        if in_architecture:
            if stripped.lower().startswith(".include"):
                includes.append(stripped)
            continue
        body.append(line)
    return "\n".join(includes + ["", *body]) + "\n"


def pulse_args(frequency_hz: float) -> tuple[float, float, float, float]:
    period = 1.0 / frequency_hz
    rise = 0.01 * period
    fall = 0.01 * period
    width = 0.49 * period
    return period, rise, fall, width


def write_external_deck(model_name: str, frequency_hz: float, load_ohm: float, case_dir: Path) -> tuple[Path, Path, Path]:
    model = MODEL_SETS[model_name]
    period, rise, fall, width = pulse_args(frequency_hz)
    stop = max(100e-6, 2.0 * period)
    step = min(10e-6, max(1e-9, period / 1000.0))
    deck = case_dir / "run.sp"
    log = case_dir / "run.log"
    wave = case_dir / "wave.txt"
    include_text = "\n".join(f'.include "{path}"' for path in model["includes"])
    instance = "M" if model_name == "openrule1um_source" else "X"
    text = f"""* TR10-1 DCDC exact source topology with external measured clock.
* Model set: {model_name}
{include_text}
.option savecurrents
VIN_SRC vin 0 12
VDD_SRC VDD 0 5
VCLK net2 0 PULSE(0 5 0 {rise:.12g} {fall:.12g} {width:.12g} {period:.12g})
{instance}M1 vin net2 net1 0 {model['nmos']} L=1u W=40u m=1
L1 net1 vout 100n
C1 vout 0 100p
{instance}M2 vin 0 net1 0 {model['nmos']} L=3u W=40u m=1
{instance}M3 net1 0 0 0 {model['nmos']} L=3u W=40u m=1
RLOAD vout 0 {load_ohm:.12g}
.control
set noaskquit
tran {step:.12g} {stop:.12g}
wrdata {wave} v(vout) i(VIN_SRC) v(net2)
.endc
.end
"""
    deck.write_text(text)
    return deck, log, wave


def write_integrated_deck(clean_source: Path, case_dir: Path) -> tuple[Path, Path, Path]:
    deck = case_dir / "run.sp"
    log = case_dir / "run.log"
    wave = case_dir / "wave.txt"
    deck.write_text(
        f"""* TR10-1 exact OpenRule1um source-level integrated DCDC/VCO reference.
.include "{clean_source}"
XTB dcdc_down_full_tb
.control
set noaskquit
tran 1n 100u
wrdata {wave} v(xtb.vout) v(xtb.net2)
.endc
.end
"""
    )
    return deck, log, wave


def run_ngspice(deck: Path, log: Path, case_dir: Path) -> int:
    completed = subprocess.run(
        ["ngspice", "-b", "-o", str(log), str(deck)],
        cwd=case_dir,
        check=False,
        timeout=900,
    )
    return completed.returncode


def load_pairs(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open() as handle:
        for line in handle:
            fields = line.split()
            if not fields:
                continue
            try:
                rows.append([float(value) for value in fields])
            except ValueError:
                continue
    if not rows:
        raise RuntimeError(f"empty waveform export: {path}")
    return rows


def time_weighted_mean(times: list[float], values: list[float], start: float) -> float:
    points = [(t, v) for t, v in zip(times, values) if t >= start]
    if len(points) < 2:
        return sum(values) / len(values)
    area = 0.0
    duration = points[-1][0] - points[0][0]
    if duration <= 0:
        return sum(v for _, v in points) / len(points)
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        area += 0.5 * (v0 + v1) * (t1 - t0)
    return area / duration


def paired_metrics(rows: list[list[float]], stop: float, load_ohm: float) -> dict[str, float]:
    if len(rows[0]) < 6:
        raise RuntimeError("expected three time/value pairs in waveform export")
    times = [row[0] for row in rows]
    vout = [row[1] for row in rows]
    iin = [row[3] for row in rows]
    start = 0.9 * stop
    tail = [value for time, value in zip(times, vout) if time >= start]
    tail_i = [value for time, value in zip(times, iin) if time >= start]
    vout_avg = time_weighted_mean(times, vout, start)
    iin_source_avg = time_weighted_mean(times, iin, start)
    input_current_delivered = -iin_source_avg
    input_power = 12.0 * input_current_delivered
    output_power = (vout_avg * vout_avg) / load_ohm
    return {
        "vout_final_V": vout[-1],
        "vout_tail_avg_V": vout_avg,
        "vout_tail_min_V": min(tail),
        "vout_tail_max_V": max(tail),
        "vout_tail_ripple_V": max(tail) - min(tail),
        "iin_source_tail_avg_A": iin_source_avg,
        "input_current_delivered_A": input_current_delivered,
        "input_power_W": input_power,
        "output_power_W": output_power,
        "efficiency_percent": 100.0 * output_power / input_power if input_power > 0 else None,
        "sample_count": len(rows),
    }


def crossing_frequency(rows: list[list[float]], start: float, level: float = 2.5) -> float | None:
    crossings: list[float] = []
    previous: tuple[float, float] | None = None
    for row in rows:
        t, value = row[0], row[1]
        if t < start:
            continue
        if previous is not None:
            t0, v0 = previous
            if v0 < level <= value and value != v0:
                crossings.append(t0 + (level - v0) * (t - t0) / (value - v0))
        previous = (t, value)
    if len(crossings) < 3:
        return None
    periods = [b - a for a, b in zip(crossings[-21:-1], crossings[-20:]) if b > a]
    if not periods:
        return None
    return 1.0 / (sum(periods) / len(periods))


def main() -> None:
    if not SOURCE_NETLIST.is_file():
        raise SystemExit(f"missing Xschem netlist: {SOURCE_NETLIST}")
    if not CURRENT_MODELS.is_file():
        raise SystemExit(f"missing current model set: {CURRENT_MODELS}")
    OUT.mkdir(parents=True, exist_ok=True)
    source_copy = OUT / "dcdc_down_full_tb.xschem.sp"
    clean_copy = OUT / "dcdc_down_full_tb.clean.sp"
    source_copy.write_text(SOURCE_NETLIST.read_text())
    clean_copy.write_text(clean_xschem_netlist(source_copy.read_text()))

    rows: list[dict[str, object]] = []
    for model_name in MODEL_SETS:
        for frequency in FREQUENCIES:
            frequency_hz = float(frequency["frequency_Hz"])
            for load_ohm in LOADS_OHM:
                case_dir = OUT / "external" / model_name / f"{frequency['label']}_r_{load_ohm:g}"
                case_dir.mkdir(parents=True, exist_ok=True)
                deck, log, wave = write_external_deck(model_name, frequency_hz, load_ohm, case_dir)
                returncode = run_ngspice(deck, log, case_dir)
                row: dict[str, object] = {
                    "model_set": model_name,
                    "clock_label": frequency["label"],
                    "vctrl_V": frequency["vctrl_V"],
                    "clock_frequency_Hz": frequency_hz,
                    "load_ohm": load_ohm,
                    "returncode": returncode,
                    "deck": str(deck),
                    "log": str(log),
                    "waveform": str(wave),
                }
                if returncode == 0 and wave.is_file():
                    stop = max(100e-6, 2.0 / frequency_hz)
                    row["measurements"] = paired_metrics(load_pairs(wave), stop, load_ohm)
                else:
                    row["measurements"] = None
                rows.append(row)

    integrated_dir = OUT / "integrated_openrule1um_vctrl_5V"
    integrated_dir.mkdir(parents=True, exist_ok=True)
    deck, log, wave = write_integrated_deck(clean_copy, integrated_dir)
    returncode = run_ngspice(deck, log, integrated_dir)
    integrated: dict[str, object] = {
        "model_set": "openrule1um_source",
        "vctrl_V": 5.0,
        "vdd_V": 5.0,
        "vin_V": 12.0,
        "load_ohm": None,
        "output_cap_F": 100e-12,
        "inductor_H": 100e-9,
        "returncode": returncode,
        "deck": str(deck),
        "log": str(log),
        "waveform": str(wave),
    }
    if returncode == 0 and wave.is_file():
        parsed = load_pairs(wave)
        times = [row[0] for row in parsed]
        vout = [row[1] for row in parsed]
        net2 = [row[3] for row in parsed]
        tail = [value for time, value in zip(times, vout) if time >= 90e-6]
        integrated["measurements"] = {
            "vout_final_V": vout[-1],
            "vout_tail_avg_V": time_weighted_mean(times, vout, 90e-6),
            "vout_tail_min_V": min(tail),
            "vout_tail_max_V": max(tail),
            "vout_tail_ripple_V": max(tail) - min(tail),
            "vco_output_frequency_Hz": crossing_frequency(
                [[t, value, t, value, t, value] for t, value in zip(times, net2)],
                10e-6,
            ),
            "sample_count": len(parsed),
        }
    else:
        integrated["measurements"] = None

    results = {
        "schema": 1,
        "status": "completed" if all(row["returncode"] == 0 for row in rows) and returncode == 0 else "incomplete",
        "source": {
            "source_schematic": str(SOURCE_SCHEMATIC),
            "xschem_netlist": str(source_copy),
            "clean_netlist": str(clean_copy),
            "xschem_version": "3.4.7 (nix-shell from /Users/yanlu/Documents/cace)",
            "source_netlist_sha256": sha256(source_copy),
            "topology": {
                "vin_V": 12.0,
                "vdd_V": 5.0,
                "inductor_H": 100e-9,
                "output_cap_F": 100e-12,
                "switch_geometry": {"M1_W_um": 40.0, "M1_L_um": 1.0, "M2_W_um": 40.0, "M2_L_um": 3.0, "M3_W_um": 40.0, "M3_L_um": 3.0},
                "source_devices": ["M1", "M2", "M3", "L1", "C1"],
                "diode_in_current_checked_in_source": False,
            },
        },
        "measurement_inputs": {
            "images": [
                "/tmp/TR10-1/images/2024_dcdc_down_vco_0_5v.png",
                "/tmp/TR10-1/images/2024_dcdc_down_vco_2_5v.png",
                "/tmp/TR10-1/images/2024_dcdc_down_vco_5_0v.png",
            ],
            "frequencies_Hz": FREQUENCIES,
        },
        "model_sets": {
            name: {"includes": [str(path) for path in spec["includes"]], "mapping": spec["mapping"]}
            for name, spec in MODEL_SETS.items()
        },
        "external_clock_rows": rows,
        "integrated_openrule1um_source_row": integrated,
        "limitations": [
            "OpenRule1um rows are historical source-level model references, not current TR-1um silicon calibration.",
            "TR-1um mapped rows are an explicit engineering device-name/model conversion; they do not constitute foundry-qualified analog LVS or RCX.",
            "The measured clock is injected externally for DCDC separation; this does not calibrate the VCO model.",
            "No package, bondwire, board, oscilloscope probe, ESR, or DCR model is included.",
            "The checked-in dcdc_down_full_tb source netlist contains M1/M2/M3 and no diode instance; the diode shown in an older slide is not silently added.",
        ],
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": results["status"], "rows": len(rows), "output": str(OUT / "results.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
