#!/usr/bin/env python3
"""Compare the canonical TR10-1 VCO post-layout deck with measured traces.

The measured frequencies are the WaveForms cursor values documented in the
original TR10-1 measurement README.  The simulation uses the checked-in
engineering post-layout deck without an external output/probe load because
that load is not reported by the measurement record.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_POSTLAYOUT = HERE / "remediated" / "vco" / "vco.post.sp"
DEFAULT_OUTROOT = HERE / "remediated" / "vco" / "measurement_comparison"

NUMBER = r"([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)"
MEASURE_KEYS = ("period_s", "frequency_Hz", "vout_min_V", "vout_max_V")
MEASURED = (
    {
        "vctrl_V": 0.5,
        "frequency_Hz": 1.652357852,
        "image": "images/2024_dcdc_down_vco_0_5v.png",
    },
    {
        "vctrl_V": 2.5,
        "frequency_Hz": 20170.90997,
        "image": "images/2024_dcdc_down_vco_2_5v.png",
    },
    {
        "vctrl_V": 5.0,
        "frequency_Hz": 33736.669,
        "image": "images/2024_dcdc_down_vco_5_0v.png",
    },
)
MEASURED_BY_CONTROL = {round(float(row["vctrl_V"]), 9): row for row in MEASURED}



def _repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _parse_measurements(text: str) -> dict[str, float | int | None]:
    result: dict[str, float | int | None] = {}
    for key in MEASURE_KEYS:
        match = re.search(
            rf"^\s*{key}\s*=\s*{NUMBER}", text, re.IGNORECASE | re.MULTILINE
        )
        result[key] = float(match.group(1)) if match else None
    rows = re.search(r"^No\. of Data Rows\s*:\s*(\d+)", text, re.IGNORECASE | re.MULTILINE)
    result["data_rows"] = int(rows.group(1)) if rows else None
    return result


def _testbench(postlayout: Path, vctrl: float, stop: str, load_cap: float) -> str:
    return (
        "* TR10-1 VCO post-layout versus WaveForms measurement comparison.\n"
        f'.include "{postlayout.resolve()}"\n\n'
        "VDDSRC PWR_SRC 0 5\n"
        "RVDD PWR_SRC PWR 1\n"
        f"VCTRLNSRC CTRLN_SRC 0 {vctrl:.12g}\n"
        "RCTRLN CTRLN_SRC P17 10\n"
        f"VCTRLPSRC CTRLP_SRC 0 {vctrl:.12g}\n"
        "RCTRLP CTRLP_SRC P22 10\n\n"
        "XU OUT PWR PWR 0 0 P17 P22 VCO\n"
        f"CLOAD OUT 0 {load_cap:.12g}\n\n"
        ".options reltol=2e-3 abstol=1e-12 vntol=1e-6 method=gear "
        "gmin=1e-10 rshunt=1e12 trtol=7 itl4=10000\n"
        ".save v(OUT) v(PWR) v(P17) v(P22)\n"
        f".tran 50n {stop} uic\n"
        ".meas tran T1 WHEN v(OUT)=2.5 RISE=2\n"
        ".meas tran T2 WHEN v(OUT)=2.5 RISE=3\n"
        ".meas tran PERIOD PARAM='T2-T1'\n"
        ".meas tran FREQ PARAM='1/PERIOD'\n"
        f".meas tran VOUT_MIN MIN v(OUT) FROM=10u TO={stop}\n"
        f".meas tran VOUT_MAX MAX v(OUT) FROM=10u TO={stop}\n"
        ".end\n"
    )


def _compare(measured_hz: float, simulated_hz: float | None) -> dict[str, Any]:
    if simulated_hz is None or not math.isfinite(simulated_hz) or simulated_hz <= 0:
        return {
            "simulated_frequency_Hz": simulated_hz,
            "frequency_ratio_sim_over_measured": None,
            "relative_error_percent": None,
            "status": "no_valid_simulated_frequency",
        }
    return {
        "simulated_frequency_Hz": simulated_hz,
        "frequency_ratio_sim_over_measured": simulated_hz / measured_hz,
        "relative_error_percent": 100.0 * (simulated_hz - measured_hz) / measured_hz,
        "status": "compared",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--postlayout", type=Path, default=DEFAULT_POSTLAYOUT)
    parser.add_argument("--outroot", type=Path, default=DEFAULT_OUTROOT)
    parser.add_argument("--stop", default="25u", help="ngspice transient stop time")
    parser.add_argument(
        "--controls",
        nargs="+",
        type=float,
        default=[2.5, 5.0],
        help="VCTRL values to simulate; default omits the 0.5 V, 1.65 Hz point",
    )
    parser.add_argument("--load-cap", type=float, default=0.0, help="external OUT load in farads")
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.0,
        help="per-run timeout in seconds; zero waits without an automatic kill",
    )
    args = parser.parse_args()

    requested_controls = {round(value, 9) for value in args.controls}
    unknown_controls = requested_controls - set(MEASURED_BY_CONTROL)
    if unknown_controls:
        raise ValueError(f"unsupported VCTRL values: {sorted(unknown_controls)}")

    selected_measurements = [
        row for row in MEASURED if round(float(row["vctrl_V"]), 9) in requested_controls
    ]
    excluded_measurements = [
        {
            "vctrl_V": row["vctrl_V"],
            "frequency_Hz": row["frequency_Hz"],
            "image": row["image"],
            "reason": "The measured 1.65 Hz period requires a much longer transient than this bounded comparison.",
        }
        for row in MEASURED
        if round(float(row["vctrl_V"]), 9) not in requested_controls
    ]

    if not selected_measurements:
        raise ValueError("at least one VCTRL value must be selected")

    if not args.postlayout.is_file():
        raise FileNotFoundError(f"post-layout deck not found: {args.postlayout}")
    if args.load_cap < 0:
        raise ValueError("--load-cap must be non-negative")
    if args.timeout < 0:
        raise ValueError("--timeout must be non-negative")

    args.outroot.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for measurement in selected_measurements:
        vctrl = float(measurement["vctrl_V"])
        tag = f"vctrl_{vctrl:g}"
        directory = args.outroot / tag
        directory.mkdir(parents=True, exist_ok=True)
        deck = directory / "run.sp"
        log = directory / "run.log"
        deck.write_text(_testbench(args.postlayout, vctrl, args.stop, args.load_cap), encoding="utf-8")

        timed_out = False
        try:
            run_kwargs: dict[str, Any] = {"check": False}
            if args.timeout > 0:
                run_kwargs["timeout"] = args.timeout
            completed = subprocess.run(
                ["ngspice", "-b", "-o", str(log), str(deck)],
                **run_kwargs,
            )
            returncode = completed.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = None
            with log.open("a", encoding="utf-8") as stream:
                stream.write(f"\nComparison runner timeout after {args.timeout:g} s.\n")

        log_text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        measurements = _parse_measurements(log_text)
        simulated_hz = measurements["frequency_Hz"]
        comparison = _compare(float(measurement["frequency_Hz"]), simulated_hz if isinstance(simulated_hz, float) else None)
        if timed_out:
            status = "timeout"
        elif returncode != 0:
            status = "simulation_failed"
        elif comparison["status"] == "compared":
            status = "compared"
        else:
            status = "completed_no_valid_frequency"

        rows.append(
            {
                "vctrl_V": vctrl,
                "measurement": {
                    "frequency_Hz": measurement["frequency_Hz"],
                    "image": measurement["image"],
                    "method": "WaveForms cursor reciprocal 1/delta-X",
                },
                "simulation": {
                    "deck": _repo_path(deck),
                    "log": _repo_path(log),
                    "returncode": returncode,
                    "status": status,
                    "measurements": measurements,
                },
                "comparison": comparison,
            }
        )


    manifest = {
        "schema": 1,
        "status": "engineering_postlayout_measurement_comparison",
        "design": "TR10-1 VCO",
        "purpose": "Compare selected canonical post-layout VCO control points against the measured WaveForms frequencies.",
        "postlayout_spice": _repo_path(args.postlayout),
        "model_bundle": "ip62_models_calibrated, included by vco.post.sp",
        "testbench": {
            "vdd_V": 5.0,
            "vctrl_V": [row["vctrl_V"] for row in rows],
            "external_output_load_F": args.load_cap,
            "transient_stop": args.stop,
            "transient_max_step": "50n",
            "initial_condition": "uic",
        },
        "measurement_source": {
            "repository": "https://github.com/ishi-kai/ISHI-KAI_Multiple_Projects_OpenMPW_TR10-1",
            "section": "README.md: VCO measurement under the DCDC section",
            "note": "The DCDC output itself is reported as having no successful output; this comparison is VCO-only.",
        },
        "rows": rows,
        "excluded_measurements": excluded_measurements,
        "limitations": [
            "The PEX network is an engineering estimate, not foundry-qualified RCX.",
            "The post-layout deck has no pad, bondwire, board, probe, or measured output-load topology.",
            "The compact-model bundle differs from the historical nchor1ex/pchor1ex source-level model used by the original TR10 VCO deck.",
            "Measured frequencies are cursor values transcribed from screenshots; raw waveform files and uncertainty are unavailable.",
            "A missing simulated frequency means no two threshold crossings occurred within the finite transient window; it is not evidence of a proven DC operating point.",
        ],
    }
    manifest_path = args.outroot / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": _repo_path(manifest_path), "rows": len(rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
