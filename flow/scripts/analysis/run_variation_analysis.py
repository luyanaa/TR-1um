#!/usr/bin/env python3
"""Run engineering PVT, pseudo-Monte Carlo, and sensitivity analyses.

The runner is contract-driven and uses real ngspice executions for the compact
model probe.  It separates execution status from review status: complete
reference-only analyses are reported as PASS_WITH_WARNINGS, while failed
executions remain FAIL.

Supported analyses:

* PVT: FF/SS/FS/SF (plus an explicit TT reference) crossed with voltage and
  temperature points.
* pseudo-Monte Carlo: deterministic, independently sampled bounded normal
  distributions for V_th, mu_0, and R_sq proxies.
* sensitivity: one-factor-at-a-time low/nominal/high runs, plus a derived
  GND-return sensitivity based on the checked-in PDN bridge estimate.

No simulator result is synthesized when a deck fails or a measurement is
missing.  The report records the exact sampled values and the failure reason.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
NUMBER_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
MEASURE_RE = re.compile(rf"(?im)^\s*i\((vmon|vps|vres)\)\s*=\s*({NUMBER_RE})")
TEMP_RE = re.compile(rf"(?im)Doing analysis at TEMP\s*=\s*({NUMBER_RE})")
ERROR_RE = re.compile(
    r"(?im)^(?:\s*error|\s*fatal):|simulation interrupted|"
    r"unknown subckt|undefined parameter|cannot compute substitute|"
    r"singular matrix|no convergence"
)
MODEL_RE = re.compile(r"^\s*\.model\s+(\S+)", re.IGNORECASE)
U0_RE = re.compile(r"(\bu0\s*=\s*)([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", re.IGNORECASE)

MODEL_SCALE_GROUPS = {
    "PMOS_mst": "p",
    "MPE_mst": "p",
    "NMOS_mst": "n",
    "MNE_mst": "n",
}


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def number(value: Any, label: str) -> float:
    if not finite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def resolve(base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def load_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read variation contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("ERROR: variation contract must be a JSON object")
    return value


def validate_process_corner(corner: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(corner, dict):
        return [f"{label} must be an object"]
    if not isinstance(corner.get("name"), str) or not corner["name"]:
        errors.append(f"{label}.name is required")
    for key in ("vth_n_shift_v", "vth_p_shift_v", "mu_n_scale", "mu_p_scale", "rs_scale"):
        if not finite(corner.get(key)):
            errors.append(f"{label}.{key} must be finite")
        elif key.endswith("scale") and float(corner[key]) <= 0:
            errors.append(f"{label}.{key} must be positive")
    return errors


def validate_distribution(entry: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"{label} must be an object"]
    if entry.get("distribution") != "normal":
        errors.append(f"{label}.distribution must be normal")
    for key in ("mean", "sigma"):
        if not finite(entry.get(key)):
            errors.append(f"{label}.{key} must be finite")
    if finite(entry.get("sigma")) and float(entry["sigma"]) <= 0:
        errors.append(f"{label}.sigma must be positive")
    bounds = entry.get("bounds")
    if not isinstance(bounds, list) or len(bounds) != 2 or not all(finite(item) for item in bounds):
        errors.append(f"{label}.bounds must be [low, high] finite numbers")
    elif float(bounds[0]) >= float(bounds[1]):
        errors.append(f"{label}.bounds must be strictly increasing")
    return errors


def validate(contract: dict[str, Any], contract_path: Path) -> list[str]:
    errors: list[str] = []
    if contract.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(contract.get("design"), str) or not contract["design"]:
        errors.append("design must be a non-empty string")
    if contract.get("qualification_status") not in {"engineering_only", "reference_only", "not_qualified"}:
        errors.append("qualification_status must be engineering_only, reference_only, or not_qualified")
    models = contract.get("model_sources")
    if not isinstance(models, dict):
        errors.append("model_sources must be an object")
    else:
        for key in ("mos", "resistor"):
            path = resolve(contract_path.parent, models.get(key))
            if path is None or not path.is_file() or path.stat().st_size == 0:
                errors.append(f"missing or empty model_sources.{key}: {path or models.get(key)}")
    probe = contract.get("probe")
    if not isinstance(probe, dict):
        errors.append("probe must be an object")
    else:
        for key in ("mos_width_um", "mos_length_um", "resistor_width_um", "resistor_length_um", "resistor_voltage_v"):
            if not finite(probe.get(key)):
                errors.append(f"probe.{key} must be finite")
            elif float(probe[key]) <= 0:
                errors.append(f"probe.{key} must be positive")
    pvt = contract.get("pvt")
    if not isinstance(pvt, dict):
        errors.append("pvt must be an object")
    else:
        corners = pvt.get("process_corners")
        if not isinstance(corners, list) or not corners:
            errors.append("pvt.process_corners must be non-empty")
        else:
            names: set[str] = set()
            for index, corner in enumerate(corners):
                errors.extend(validate_process_corner(corner, f"pvt.process_corners[{index}]"))
                if isinstance(corner, dict) and isinstance(corner.get("name"), str):
                    if corner["name"] in names:
                        errors.append(f"duplicate PVT process corner: {corner['name']}")
                    names.add(corner["name"])
        for key in ("voltages_v", "temperatures_c"):
            values = pvt.get(key)
            if not isinstance(values, list) or not values or not all(finite(item) for item in values):
                errors.append(f"pvt.{key} must be a non-empty finite numeric list")
    mc = contract.get("monte_carlo")
    if not isinstance(mc, dict):
        errors.append("monte_carlo must be an object")
    else:
        if not isinstance(mc.get("samples"), int) or mc["samples"] < 1:
            errors.append("monte_carlo.samples must be a positive integer")
        if not isinstance(mc.get("seed"), int):
            errors.append("monte_carlo.seed must be an integer")
        if mc.get("correlation") != "independent":
            errors.append("monte_carlo.correlation must be independent")
        parameters = mc.get("parameters")
        if not isinstance(parameters, list) or not parameters:
            errors.append("monte_carlo.parameters must be non-empty")
        else:
            names: set[str] = set()
            for index, item in enumerate(parameters):
                label = f"monte_carlo.parameters[{index}]"
                errors.extend(validate_distribution(item, label))
                if isinstance(item, dict):
                    name = item.get("name")
                    key = item.get("key")
                    if not isinstance(name, str) or not name:
                        errors.append(f"{label}.name is required")
                    elif name in names:
                        errors.append(f"duplicate Monte Carlo parameter: {name}")
                    names.add(name)
                    if key not in {"vth_n_shift_v", "vth_p_shift_v", "mu_n_scale", "mu_p_scale", "rs_scale"}:
                        errors.append(f"{label}.key is not a supported model parameter")
        fixed = mc.get("fixed")
        if not isinstance(fixed, dict) or not finite(fixed.get("vdd_v")) or not finite(fixed.get("temperature_c")):
            errors.append("monte_carlo.fixed must declare finite vdd_v and temperature_c")
    sensitivity = contract.get("sensitivity")
    if not isinstance(sensitivity, dict):
        errors.append("sensitivity must be an object")
    else:
        baseline = sensitivity.get("baseline")
        if not isinstance(baseline, dict):
            errors.append("sensitivity.baseline must be an object")
        factors = sensitivity.get("factors")
        if not isinstance(factors, list) or not factors:
            errors.append("sensitivity.factors must be non-empty")
        else:
            for index, factor in enumerate(factors):
                label = f"sensitivity.factors[{index}]"
                if not isinstance(factor, dict):
                    errors.append(f"{label} must be an object")
                    continue
                for key in ("name", "key", "units"):
                    if not isinstance(factor.get(key), str) or not factor[key]:
                        errors.append(f"{label}.{key} is required")
                for key in ("low", "nominal", "high"):
                    if not finite(factor.get(key)):
                        errors.append(f"{label}.{key} must be finite")
                if all(finite(factor.get(key)) for key in ("low", "nominal", "high")):
                    if not float(factor["low"]) < float(factor["nominal"]) < float(factor["high"]):
                        errors.append(f"{label} requires low < nominal < high")
                if factor.get("evaluation", "spice") not in {"spice", "return_path"}:
                    errors.append(f"{label}.evaluation must be spice or return_path")
        return_path = sensitivity.get("return_path")
        if not isinstance(return_path, dict):
            errors.append("sensitivity.return_path must be an object")
        else:
            report = resolve(contract_path.parent, return_path.get("pdn_report"))
            if report is None or not report.is_file() or report.stat().st_size == 0:
                errors.append(f"missing or empty sensitivity.return_path.pdn_report: {report or return_path.get('pdn_report')}")
            if not isinstance(return_path.get("load_current_path"), str) or not return_path["load_current_path"]:
                errors.append("sensitivity.return_path.load_current_path is required")
    timing = contract.get("timing_sensitivity")
    if timing is not None:
        if not isinstance(timing, dict):
            errors.append("timing_sensitivity must be an object")
        else:
            timing_report = resolve(contract_path.parent, timing.get("report"))
            if timing_report is None or not timing_report.is_file() or timing_report.stat().st_size == 0:
                errors.append(
                    f"missing or empty timing_sensitivity.report: {timing_report or timing.get('report')}"
                )
    return errors


def spice_number(value: Any) -> str:
    return f"{float(value):.17g}"


def transform_mos_model(source: Path, destination: Path, mu_n_scale: float, mu_p_scale: float) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    output: list[str] = []
    active_model: str | None = None
    for line in lines:
        match = MODEL_RE.match(line)
        if match:
            active_model = match.group(1)
        elif active_model is not None and line.strip() and not line.lstrip().startswith(("+", "*")):
            active_model = None
        if active_model in MODEL_SCALE_GROUPS and line.lstrip().startswith("+") and U0_RE.search(line):
            scale = mu_n_scale if MODEL_SCALE_GROUPS[active_model] == "n" else mu_p_scale

            def replace(match: re.Match[str]) -> str:
                return f"{match.group(1)}{float(match.group(2)) * scale:.17g}"

            line = U0_RE.sub(replace, line)
        output.append(line)
    destination.write_text("\n".join(output) + "\n", encoding="utf-8")


def render_deck(
    contract: dict[str, Any],
    mos_model: Path,
    vdd_v: float,
    temperature_c: float,
    params: dict[str, float],
) -> str:
    probe = contract["probe"]
    resistor_model = resolve(Path(contract["_contract_path"]).parent, contract["model_sources"]["resistor"])
    if resistor_model is None:
        raise ValueError("resistor model path is missing")
    return "\n".join(
        [
            "* Generated variation-analysis probe; do not hand-edit.",
            f".param vthMP={spice_number(params['vth_p_shift_v'])} vthMN={spice_number(params['vth_n_shift_v'])} "
            f"vthMPE={spice_number(params['vth_p_shift_v'])} vthMNE={spice_number(params['vth_n_shift_v'])}",
            f".param magRS={spice_number(params['rs_scale'])}",
            f".temp {spice_number(temperature_c)}",
            f".include '{mos_model.as_posix()}'",
            f".include '{resistor_model.as_posix()}'",
            f"VDD VDD 0 {spice_number(vdd_v)}",
            f"VMON ND 0 {spice_number(vdd_v)}",
            f"VGN VG 0 {spice_number(vdd_v)}",
            "VSN NS 0 0",
            "VBN NB 0 0",
            f"XN ND VG NS NB NMOS w={spice_number(probe['mos_width_um'])}u l={spice_number(probe['mos_length_um'])}u",
            "VPS PS 0 {0}".format(spice_number(vdd_v)),
            "VGP PG 0 0",
            "VDP DP 0 0",
            f"XP DP PG PS PS PMOS w={spice_number(probe['mos_width_um'])}u l={spice_number(probe['mos_length_um'])}u",
            f"VRES RP 0 {spice_number(probe['resistor_voltage_v'])}",
            f"XRS RP 0 F_RS w={spice_number(probe['resistor_width_um'])}u l={spice_number(probe['resistor_length_um'])}u",
            ".op",
            ".control",
            "set noaskquit",
            "run",
            "print i(VMON) i(VPS) i(VRES)",
            ".endc",
            ".end",
            "",
        ]
    )


def parse_measurements(text: str, resistor_voltage_v: float) -> tuple[dict[str, float], list[str]]:
    values: dict[str, float] = {}
    for name, raw in MEASURE_RE.findall(text):
        value = float(raw)
        if not math.isfinite(value):
            continue
        values[{"vmon": "nmos_current_a", "vps": "pmos_current_a", "vres": "rs_current_a"}[name.lower()]] = abs(value)
    if "rs_current_a" in values and values["rs_current_a"] > 0:
        values["rs_resistance_ohm"] = abs(resistor_voltage_v / values["rs_current_a"])
    errors: list[str] = []
    for key in ("nmos_current_a", "pmos_current_a", "rs_current_a", "rs_resistance_ohm"):
        if key not in values:
            errors.append(f"missing measurement: {key}")
    return values, errors


def run_case(
    contract: dict[str, Any],
    workdir: Path,
    case_id: str,
    vdd_v: float,
    temperature_c: float,
    params: dict[str, float],
    process_name: str,
    ngspice: str,
) -> dict[str, Any]:
    model_sources = contract["model_sources"]
    mos_source = resolve(Path(contract["_contract_path"]).parent, model_sources["mos"])
    if mos_source is None:
        raise ValueError("MOS model path is missing")
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", case_id)
    model_path = workdir / f"{safe_id}.mos.lib"
    deck_path = workdir / f"{safe_id}.cir"
    log_path = workdir / f"{safe_id}.log"
    transform_mos_model(mos_source, model_path, params["mu_n_scale"], params["mu_p_scale"])
    deck_path.write_text(render_deck(contract, model_path, vdd_v, temperature_c, params), encoding="utf-8")
    result: dict[str, Any] = {
        "case": case_id,
        "process": process_name,
        "vdd_v": vdd_v,
        "temperature_c": temperature_c,
        "parameters": dict(params),
        "status": "FAIL",
        "returncode": None,
        "measurements": {},
        "errors": [],
    }
    try:
        completed = subprocess.run(
            [ngspice, "-b", "-o", str(log_path), str(deck_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["errors"].append(f"cannot run ngspice: {exc}")
        return result
    text = (log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else "")
    text += "\n" + completed.stdout + "\n" + completed.stderr
    result["returncode"] = completed.returncode
    if completed.returncode != 0:
        result["errors"].append(f"ngspice returned {completed.returncode}")
    if ERROR_RE.search(text):
        result["errors"].append("ngspice reported a simulation error")
    requested_temperature = [float(item) for item in TEMP_RE.findall(text)]
    if not any(math.isclose(value, temperature_c, abs_tol=1e-9) for value in requested_temperature):
        result["errors"].append(f"ngspice did not report requested temperature {temperature_c:g}C")
    measurements, measurement_errors = parse_measurements(text, float(contract["probe"]["resistor_voltage_v"]))
    result["measurements"] = measurements
    result["errors"].extend(measurement_errors)
    rs_limit = contract.get("limits", {}).get("rs_current_abs_max_a")
    if finite(rs_limit) and finite(measurements.get("rs_current_a")) and measurements["rs_current_a"] > float(rs_limit):
        result["errors"].append(
            f"rs_current_a {measurements['rs_current_a']:.6g} exceeds engineering limit {float(rs_limit):.6g}"
        )
    if not result["errors"]:
        result["status"] = "PASS"
    else:
        result["log_tail"] = text[-2000:]
    return result


def default_params() -> dict[str, float]:
    return {
        "vth_n_shift_v": 0.0,
        "vth_p_shift_v": 0.0,
        "mu_n_scale": 1.0,
        "mu_p_scale": 1.0,
        "rs_scale": 1.0,
    }


def pvt_cases(contract: dict[str, Any]) -> list[tuple[str, float, float, dict[str, float], str]]:
    result: list[tuple[str, float, float, dict[str, float], str]] = []
    pvt = contract["pvt"]
    for corner in pvt["process_corners"]:
        params = {
            "vth_n_shift_v": float(corner["vth_n_shift_v"]),
            "vth_p_shift_v": float(corner["vth_p_shift_v"]),
            "mu_n_scale": float(corner["mu_n_scale"]),
            "mu_p_scale": float(corner["mu_p_scale"]),
            "rs_scale": float(corner["rs_scale"]),
        }
        for vdd_v in pvt["voltages_v"]:
            for temperature_c in pvt["temperatures_c"]:
                case_id = f"pvt_{corner['name']}_v{float(vdd_v):g}_t{float(temperature_c):g}"
                result.append((case_id, float(vdd_v), float(temperature_c), params, str(corner["name"])))
    return result


def sample_bounded_normal(rng: random.Random, mean: float, sigma: float, bounds: list[float]) -> float:
    low, high = float(bounds[0]), float(bounds[1])
    for _ in range(10000):
        value = rng.gauss(mean, sigma)
        if low <= value <= high:
            return value
    raise RuntimeError(f"bounded normal sampling failed after 10000 attempts for [{low}, {high}]")


def monte_carlo_cases(contract: dict[str, Any]) -> list[tuple[str, float, float, dict[str, float], str]]:
    mc = contract["monte_carlo"]
    rng = random.Random(int(mc["seed"]))
    result: list[tuple[str, float, float, dict[str, float], str]] = []
    fixed = mc["fixed"]
    for index in range(int(mc["samples"])):
        params = default_params()
        for entry in mc["parameters"]:
            params[str(entry["key"])] = sample_bounded_normal(
                rng, float(entry["mean"]), float(entry["sigma"]), [float(item) for item in entry["bounds"]]
            )
        result.append((f"mc_{index:04d}", float(fixed["vdd_v"]), float(fixed["temperature_c"]), params, "MC"))
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc


def json_pointer(value: Any, pointer: str) -> Any:
    current = value
    for token in pointer.split("."):
        if not token:
            continue
        if not isinstance(current, dict) or token not in current:
            raise ValueError(f"JSON path not found: {pointer}")
        current = current[token]
    return current


def return_path_cases(contract: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config = contract["sensitivity"]["return_path"]
    report_path = resolve(Path(contract["_contract_path"]).parent, config["pdn_report"])
    if report_path is None:
        raise ValueError("return path PDN report path is missing")
    report = load_json(report_path)
    current_ma = number(json_pointer(report, str(config["load_current_path"])), "return-path load current")
    current_a = current_ma * float(config.get("load_current_scale", 1e-3))
    return [
        {
            "factor": "return_path_resistance_ohm",
            "metric": "ground_return_vdrop_v",
            "load_current_a": current_a,
            "source_report": str(report_path),
        }
    ], {
        "load_current_a": current_a,
        "bridge_estimate": report.get("bridge_estimate"),
    }


def sensitivity_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    numeric = [float(value) for value in rows if finite(value)]
    if not numeric:
        return {"count": 0, "min": None, "max": None, "mean": None, "stddev": None}
    return {
        "count": len(numeric),
        "min": min(numeric),
        "max": max(numeric),
        "mean": statistics.fmean(numeric),
        "stddev": statistics.stdev(numeric) if len(numeric) > 1 else 0.0,
        "p01": quantile(numeric, 0.01),
        "p05": quantile(numeric, 0.05),
        "p50": quantile(numeric, 0.50),
        "p95": quantile(numeric, 0.95),
        "p99": quantile(numeric, 0.99),
    }


def quantile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("quantile requires non-empty values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def measurement_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    keys = sorted({key for case in cases for key in case.get("measurements", {})})
    return {key: sensitivity_summary([case.get("measurements", {}).get(key) for case in cases]) for key in keys}


def metric_sensitivity(low: dict[str, Any], nominal: dict[str, Any], high: dict[str, Any]) -> dict[str, Any]:
    metrics = sorted(
        set(low.get("measurements", {}))
        | set(nominal.get("measurements", {}))
        | set(high.get("measurements", {}))
    )
    result: dict[str, Any] = {}
    normalized_effects: list[float] = []
    for metric in metrics:
        low_value = low.get("measurements", {}).get(metric)
        nominal_value = nominal.get("measurements", {}).get(metric)
        high_value = high.get("measurements", {}).get(metric)
        if not all(finite(value) for value in (low_value, nominal_value, high_value)):
            result[metric] = {"low": low_value, "nominal": nominal_value, "high": high_value, "status": "INCOMPLETE"}
            continue
        delta = float(high_value) - float(low_value)
        denominator = max(abs(float(nominal_value)), 1e-30)
        normalized = abs(delta) / denominator
        normalized_effects.append(normalized)
        result[metric] = {
            "low": low_value,
            "nominal": nominal_value,
            "high": high_value,
            "delta_high_minus_low": delta,
            "slope_per_factor_unit": delta,
            "normalized_effect": normalized,
            "status": "PASS",
        }
    return {"metrics": result, "aggregate_max_normalized_effect": max(normalized_effects) if normalized_effects else None}


def run_sensitivity(contract: dict[str, Any], workdir: Path, ngspice: str) -> dict[str, Any]:
    config = contract["sensitivity"]
    baseline = dict(config["baseline"])
    results: list[dict[str, Any]] = []
    for index, factor in enumerate(config["factors"]):
        factor_result: dict[str, Any] = {
            "name": factor["name"],
            "key": factor["key"],
            "units": factor["units"],
            "evaluation": factor.get("evaluation", "spice"),
            "points": {},
            "status": "FAIL",
            "errors": [],
        }
        if factor.get("evaluation", "spice") == "return_path":
            try:
                _, return_info = return_path_cases(contract)
                factor_result["points"] = {
                    label: {"value": float(factor[label]), "measurements": {"ground_return_vdrop_v": float(factor[label]) * return_info["load_current_a"]}, "status": "PASS"}
                    for label in ("low", "nominal", "high")
                }
                factor_result["return_path"] = return_info
                factor_result["analysis"] = {
                    "metrics": {
                        "ground_return_vdrop_v": {
                            "low": factor_result["points"]["low"]["measurements"]["ground_return_vdrop_v"],
                            "nominal": factor_result["points"]["nominal"]["measurements"]["ground_return_vdrop_v"],
                            "high": factor_result["points"]["high"]["measurements"]["ground_return_vdrop_v"],
                            "delta_high_minus_low": factor_result["points"]["high"]["measurements"]["ground_return_vdrop_v"] - factor_result["points"]["low"]["measurements"]["ground_return_vdrop_v"],
                            "slope_per_factor_unit": return_info["load_current_a"],
                            "normalized_effect": abs(factor_result["points"]["high"]["measurements"]["ground_return_vdrop_v"] - factor_result["points"]["low"]["measurements"]["ground_return_vdrop_v"]) / max(abs(factor_result["points"]["nominal"]["measurements"]["ground_return_vdrop_v"]), 1e-30),
                            "status": "PASS",
                        }
                    },
                    "aggregate_max_normalized_effect": abs(factor_result["points"]["high"]["measurements"]["ground_return_vdrop_v"] - factor_result["points"]["low"]["measurements"]["ground_return_vdrop_v"]) / max(abs(factor_result["points"]["nominal"]["measurements"]["ground_return_vdrop_v"]), 1e-30),
                }
                factor_result["status"] = "PASS"
            except (OSError, ValueError, KeyError, TypeError) as exc:
                factor_result["errors"].append(str(exc))
            results.append(factor_result)
            continue
        cases: list[dict[str, Any]] = []
        for label in ("low", "nominal", "high"):
            params = default_params()
            for key in params:
                if key in baseline:
                    params[key] = float(baseline[key])
            vdd_v = float(baseline.get("vdd_v", 5.0))
            temperature_c = float(baseline.get("temperature_c", 27.0))
            key = str(factor["key"])
            value = float(factor[label])
            if key in params:
                params[key] = value
            elif key == "vdd_v":
                vdd_v = value
            elif key == "temperature_c":
                temperature_c = value
            else:
                factor_result["errors"].append(f"unsupported sensitivity factor key: {key}")
                break
            cases.append(run_case(contract, workdir, f"sens_{index:02d}_{factor['name']}_{label}", vdd_v, temperature_c, params, "SENS", ngspice))
        if len(cases) == 3:
            factor_result["points"] = {label: case for label, case in zip(("low", "nominal", "high"), cases)}
            if all(case["status"] == "PASS" for case in cases):
                factor_result["analysis"] = metric_sensitivity(cases[0], cases[1], cases[2])
                factor_result["status"] = "PASS"
            else:
                factor_result["errors"].append("one or more sensitivity points failed")
        results.append(factor_result)
    ranking = sorted(
        [
            {
                "name": item["name"],
                "key": item["key"],
                "aggregate_max_normalized_effect": item.get("analysis", {}).get("aggregate_max_normalized_effect"),
                "status": item["status"],
            }
            for item in results
        ],
        key=lambda item: item["aggregate_max_normalized_effect"] if finite(item["aggregate_max_normalized_effect"]) else -1.0,
        reverse=True,
    )
    return {"status": "PASS" if results and all(item["status"] == "PASS" for item in results) else "FAIL", "factors": results, "ranking": ranking}


def run(contract: dict[str, Any], contract_path: Path, output: Path, ngspice: str) -> dict[str, Any]:
    contract = dict(contract)
    contract["_contract_path"] = str(contract_path.resolve())
    errors = validate(contract, contract_path)
    if shutil.which(ngspice) is None and not Path(ngspice).is_file():
        errors.append(f"ngspice executable not found: {ngspice}")
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "BLOCKED",
        "qualification_status": contract.get("qualification_status"),
        "contract": str(contract_path.resolve()),
        "design": contract.get("design"),
        "ngspice": ngspice,
        "errors": errors,
        "pvt": {"status": "BLOCKED", "cases": [], "summary": {}},
        "pseudo_monte_carlo": {"status": "BLOCKED", "cases": [], "summary": {}},
        "sensitivity": {"status": "BLOCKED", "factors": [], "ranking": []},
        "timing_sensitivity": {"status": "BLOCKED"},
        "warnings": contract.get("warnings", []),
        "limitations": contract.get("limitations", []),
    }
    if errors:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report
    with tempfile.TemporaryDirectory(prefix="tr1um-variation-analysis-") as temp_dir:
        workdir = Path(temp_dir)
        pvt_results = [run_case(contract, workdir, case_id, vdd, temp, params, process, ngspice) for case_id, vdd, temp, params, process in pvt_cases(contract)]
        mc_results = [run_case(contract, workdir, case_id, vdd, temp, params, process, ngspice) for case_id, vdd, temp, params, process in monte_carlo_cases(contract)]
        sensitivity = run_sensitivity(contract, workdir, ngspice)
    pvt_execution_status = "PASS" if pvt_results and all(case["status"] == "PASS" for case in pvt_results) else "FAIL"
    mc_execution_status = "PASS" if mc_results and all(case["status"] == "PASS" for case in mc_results) else "FAIL"
    pvt_status = "PASS_WITH_WARNINGS" if pvt_execution_status == "PASS" else "FAIL"
    mc_status = "PASS_WITH_WARNINGS" if mc_execution_status == "PASS" else "FAIL"
    report["pvt"] = {
        "status": pvt_status,
        "execution_status": pvt_execution_status,
        "warnings": contract["pvt"].get("warnings", []),
        "process_corner_names": [corner["name"] for corner in contract["pvt"]["process_corners"]],
        "voltages_v": contract["pvt"]["voltages_v"],
        "temperatures_c": contract["pvt"]["temperatures_c"],
        "case_count": len(pvt_results),
        "pass_count": sum(case["status"] == "PASS" for case in pvt_results),
        "cases": pvt_results,
        "measurement_summary": measurement_summary(pvt_results),
    }
    report["pseudo_monte_carlo"] = {
        "status": mc_status,
        "execution_status": mc_execution_status,
        "warnings": contract["monte_carlo"].get("warnings", []),
        "samples": contract["monte_carlo"]["samples"],
        "seed": contract["monte_carlo"]["seed"],
        "correlation": contract["monte_carlo"]["correlation"],
        "parameters": contract["monte_carlo"]["parameters"],
        "fixed": contract["monte_carlo"]["fixed"],
        "case_count": len(mc_results),
        "pass_count": sum(case["status"] == "PASS" for case in mc_results),
        "cases": mc_results,
        "measurement_summary": measurement_summary(mc_results),
    }
    sensitivity_execution_status = sensitivity["status"]
    sensitivity["execution_status"] = sensitivity_execution_status
    sensitivity["status"] = "PASS_WITH_WARNINGS" if sensitivity_execution_status == "PASS" else "FAIL"
    sensitivity["warnings"] = contract["sensitivity"].get("warnings", [])
    report["sensitivity"] = sensitivity
    timing_execution_status = "NOT_DECLARED"
    timing_review_status = "NOT_DECLARED"
    timing_contract = contract.get("timing_sensitivity")
    if isinstance(timing_contract, dict):
        timing_path = resolve(contract_path.parent, timing_contract.get("report"))
        if timing_path is None:
            timing_execution_status = "BLOCKED"
            timing_review_status = "BLOCKED"
            report["timing_sensitivity"] = {"status": timing_review_status, "execution_status": timing_execution_status}
        else:
            timing_data = load_json(timing_path)
            timing_execution_status = str(timing_data.get("execution_status", "FAIL"))
            timing_review_status = str(timing_data.get("status", "FAIL"))
            report["timing_sensitivity"] = {
                "status": timing_review_status,
                "execution_status": timing_execution_status,
                "warnings": timing_data.get("warnings", timing_contract.get("warnings", [])),
                "report": str(timing_path.resolve()),
                "design": timing_data.get("inputs", {}).get("top"),
                "tool": timing_data.get("tool"),
                "sampling": timing_data.get("sampling"),
                "summary": timing_data.get("summary"),
                "limitations": timing_data.get("limitations", []),
            }
    all_pass = (
        pvt_execution_status == "PASS"
        and mc_execution_status == "PASS"
        and sensitivity_execution_status == "PASS"
        and timing_execution_status in {"PASS", "NOT_DECLARED"}
    )
    report["execution_status"] = "PASS" if all_pass else "FAIL"
    report["status"] = "PASS_WITH_WARNINGS" if all_pass else "FAIL"
    report["warnings"] = list(contract.get("warnings", []))
    report["limitations"] = list(contract.get("limitations", []))
    report["limitations"].append("Reference-only FF/SS/FS/SF modifiers are not foundry process-corner model cards.")
    report["limitations"].append("Reference-only pseudo-Monte Carlo uses independent bounded normal samples; no silicon mismatch sigma or spatial correlation is claimed.")
    report["limitations"].append("Reference-only sensitivity is one-factor-at-a-time and does not establish a multivariate worst-case or qualified EM/IR limit.")
    if timing_execution_status == "PASS":
        report["limitations"].append("Timing evidence is a nominal-corner reference-only RC screen from the LibreLane shell; it is not PVT timing signoff.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ngspice", default="ngspice")
    args = parser.parse_args()
    report = run(load_contract(args.contract.resolve()), args.contract.resolve(), args.output.resolve(), args.ngspice)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS_WITH_WARNINGS" and report.get("execution_status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
