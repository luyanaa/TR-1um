#!/usr/bin/env python3
"""Run explicit analog pre/post-layout SPICE cases and enforce measured limits.

This runner never manufactures an extracted deck.  The manifest must identify
an extracted deck, the macro CDL, process models, frame/pad/ESD models, and a
digital abstraction for every case.  It also requires explicit supply,
temperature, process, load, input-slew, startup, and activity sweep entries.
Each case is tagged ``pre_layout`` or ``post_layout`` and must bind every
assertion to the central electrical-limits contract with a non-zero margin and
an explicit ngspice expression. Optional ``width_um`` plus
``density_limit_ref`` fields add engineering current-width screening:
``width_um >= I_peak / J`` and the same assertion enforces ``I_peak < I_max``
after its margin. Runtime assertions are emitted as a
``.control`` ``run``/``meas``/``if`` block because ngspice-47 treats the
suggested ``.assert ... alert=fail`` card as an undefined parameter.
A case is PASS only when ngspice completes, every declared measurement is
present and numeric, and all limits are met below the asserted margin.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from electrical_limits import finite_number, load_and_validate, resolve_limit

SCHEMA_VERSION = 1
SWEEP_AXES = (
    "supply",
    "temperature",
    "process",
    "load",
    "input_slew",
    "startup",
    "activity",
)

SAFE_ASSERTION_NAME = re.compile(r"^[A-Za-z0-9_.:-]+$")
SAFE_RUNTIME_EXPRESSION = re.compile(r"^[A-Za-z0-9_().,+*/ \t-]+$")
SAFE_RUNTIME_MESSAGE = re.compile(r"^[A-Za-z0-9_ .:/()+!=?,-]+$")
RUNTIME_DECK_END = re.compile(r"^\s*\.end(?:\s*(?:\$.*)?)?\s*$", re.IGNORECASE)
RUNTIME_CONTROL = re.compile(r"^\s*\.control\b", re.IGNORECASE)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read analog simulation manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("ERROR: analog simulation manifest must be a JSON object")
    return value


def resolve(base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def positive_number(value: Any) -> bool:
    return finite_number(value) and float(value) > 0.0


def file_error(base: Path, value: Any, label: str) -> str | None:
    path = resolve(base, value)
    if path is None:
        return f"{label} must be a non-empty path"
    if not path.is_file() or path.stat().st_size == 0:
        return f"missing or empty {label}: {path}"
    return None


def validate(
    manifest: dict[str, Any], manifest_path: Path
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any] | None]:
    base = manifest_path.parent
    errors: list[str] = []
    limits: dict[str, Any] | None = None
    limits_path = resolve(base, manifest.get("electrical_limits"))
    if limits_path is None:
        errors.append("electrical_limits must identify a machine-readable limits contract")
    else:
        try:
            limits, limit_errors = load_and_validate(limits_path)
        except SystemExit as exc:
            errors.append(str(exc))
        else:
            errors.extend(limit_errors)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not nonempty(manifest.get("design")):
        errors.append("design must be a non-empty string")
    required_axes = manifest.get("required_sweep_axes", list(SWEEP_AXES))
    if not isinstance(required_axes, list) or not required_axes or not all(axis in SWEEP_AXES for axis in required_axes):
        errors.append(f"required_sweep_axes must use known non-empty axes: {list(SWEEP_AXES)}")
        required_axes = list(SWEEP_AXES)
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("cases must be a non-empty list; no pre/post-layout simulation is a blocked result")
        cases = []
    normalized: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = case.get("name")
        if not nonempty(name):
            errors.append(f"{prefix}.name is required")
            continue
        if name in names:
            errors.append(f"duplicate case name: {name}")
        names.add(name)
        stage = case.get("stage", "post_layout")
        if stage not in {"pre_layout", "post_layout"}:
            errors.append(f"{prefix}.stage must be pre_layout or post_layout")
            stage = "post_layout"
        deck_error = file_error(base, case.get("deck"), f"{prefix}.deck")
        if deck_error:
            errors.append(deck_error)
        views = case.get("source_views")
        if not isinstance(views, dict):
            errors.append(f"{prefix}.source_views must identify all source views")
            views = {}
        normalized_views: dict[str, str] = {}
        for view in ("extracted_spice", "macro_cdl", "process_models", "frame_pad_esd_models", "digital_abstraction"):
            view_error = file_error(base, views.get(view), f"{prefix}.source_views.{view}")
            if view_error:
                errors.append(view_error)
            view_path = resolve(base, views.get(view))
            if view_path is not None:
                normalized_views[view] = str(view_path)
        sweeps = case.get("sweeps")
        if not isinstance(sweeps, dict):
            errors.append(f"{prefix}.sweeps must declare every required sweep axis")
            sweeps = {}
        for axis in required_axes:
            values = sweeps.get(axis)
            if not isinstance(values, list) or not values:
                errors.append(f"{prefix}.sweeps.{axis} must be a non-empty list")
        measures = case.get("measures")
        if not isinstance(measures, list) or not measures:
            errors.append(f"{prefix}.measures must be a non-empty list")
            measures = []
        normalized_measures: list[dict[str, Any]] = []
        for measure_index, measure in enumerate(measures):
            measure_prefix = f"{prefix}.measures[{measure_index}]"
            if not isinstance(measure, dict) or not nonempty(measure.get("name")):
                errors.append(f"{measure_prefix}.name is required")
                continue
            if not any(key in measure for key in ("min", "max")):
                errors.append(f"{measure_prefix} requires min and/or max")
            for key in ("min", "max"):
                if key in measure and not finite_number(measure[key]):
                    errors.append(f"{measure_prefix}.{key} must be finite and numeric")
            if (
                finite_number(measure.get("min"))
                and finite_number(measure.get("max"))
                and float(measure["min"]) > float(measure["max"])
            ):
                errors.append(f"{measure_prefix}.min exceeds max")
            normalized_measures.append(measure)
        assertions = case.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            errors.append(f"{prefix}.assertions must be a non-empty list of limit-bound measurements")
            assertions = []
        normalized_assertions: list[dict[str, Any]] = []
        for assertion_index, assertion in enumerate(assertions):
            assertion_prefix = f"{prefix}.assertions[{assertion_index}]"
            if not isinstance(assertion, dict):
                errors.append(f"{assertion_prefix} must be an object")
                continue
            assertion_name = assertion.get("name")
            target = assertion.get("target")
            measure_name = assertion.get("measure")
            expression = assertion.get("expression")
            message = assertion.get("message")
            limit_ref = assertion.get("limit_ref")
            density_limit_ref = assertion.get("density_limit_ref")
            if not nonempty(assertion_name):
                errors.append(f"{assertion_prefix}.name is required")
            elif not SAFE_ASSERTION_NAME.fullmatch(assertion_name.strip()):
                errors.append(f"{assertion_prefix}.name contains unsafe runtime characters")
            if not nonempty(target):
                errors.append(f"{assertion_prefix}.target is required")
            if not nonempty(measure_name):
                errors.append(f"{assertion_prefix}.measure is required")
            if not nonempty(expression):
                errors.append(f"{assertion_prefix}.expression is required for ngspice runtime assertion")
            elif not SAFE_RUNTIME_EXPRESSION.fullmatch(expression.strip()):
                errors.append(f"{assertion_prefix}.expression contains unsafe ngspice characters")
            if message is None:
                message = (
                    f"{assertion_name.strip()} Limit Exceeded!"
                    if isinstance(assertion_name, str) and assertion_name.strip()
                    else "Runtime Assertion Limit Exceeded!"
                )
            if not nonempty(message):
                errors.append(f"{assertion_prefix}.message must be non-empty when supplied")
            elif not SAFE_RUNTIME_MESSAGE.fullmatch(message.strip()):
                errors.append(f"{assertion_prefix}.message contains unsafe ngspice characters")
            if not nonempty(limit_ref):
                errors.append(f"{assertion_prefix}.limit_ref is required")
            mode = assertion.get("mode", "absolute")
            if mode not in {"absolute", "signed"}:
                errors.append(f"{assertion_prefix}.mode must be absolute or signed")
                mode = "absolute"
            margin_fraction = assertion.get("margin_fraction")
            if (
                not finite_number(margin_fraction)
                or float(margin_fraction) <= 0.0
                or float(margin_fraction) >= 1.0
            ):
                errors.append(
                    f"{assertion_prefix}.margin_fraction must be finite and strictly between 0 and 1"
                )
            width_um = assertion.get("width_um")
            if width_um is not None:
                if not positive_number(width_um):
                    errors.append(f"{assertion_prefix}.width_um must be finite and positive")
                if not nonempty(density_limit_ref):
                    errors.append(
                        f"{assertion_prefix}.density_limit_ref is required with width_um"
                    )
                elif not density_limit_ref.startswith("interconnect_limits."):
                    errors.append(
                        f"{assertion_prefix}.density_limit_ref must reference interconnect_limits"
                    )
            elif density_limit_ref is not None:
                errors.append(f"{assertion_prefix}.density_limit_ref requires width_um")
            limit = None
            if limits is not None and nonempty(limit_ref):
                limit, limit_error = resolve_limit(limits, limit_ref)
                if limit_error:
                    errors.append(f"{assertion_prefix}: {limit_error}")
            density_limit = None
            if limits is not None and nonempty(density_limit_ref):
                density_limit, density_error = resolve_limit(limits, density_limit_ref)
                if density_error:
                    errors.append(f"{assertion_prefix}: {density_error}")
            allowed = None
            if limit is not None and finite_number(margin_fraction):
                allowed = float(limit) * (1.0 - float(margin_fraction))
            normalized_assertions.append(
                {
                    "name": assertion_name,
                    "target": target,
                    "measure": measure_name,
                    "expression": expression.strip() if isinstance(expression, str) else "",
                    "message": message.strip() if isinstance(message, str) else "",
                    "limit_ref": limit_ref,
                    "limit": limit,
                    "allowed": allowed,
                    "margin_fraction": margin_fraction,
                    "mode": mode,
                    "width_um": float(width_um) if positive_number(width_um) else width_um,
                    "density_limit_ref": density_limit_ref,
                    "density_limit": density_limit,
                    "runtime_vector": f"__tr1um_assert_vector_{assertion_index}",
                    "runtime_measure": f"__tr1um_assert_{assertion_index}",
                }
            )
        normalized.append(
            {
                "name": name,
                "stage": stage,
                "deck": resolve(base, case.get("deck")),
                "source_views": normalized_views,
                "sweeps": sweeps,
                "measures": normalized_measures,
                "assertions": normalized_assertions,
            }
        )
    return normalized, errors, limits


def parse_measurements(text: str) -> tuple[dict[str, float], list[str]]:
    values: dict[str, float] = {}
    failed: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*=\s*([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)(?:\s|$)", line)
        if match:
            values[match.group(1).lower()] = float(match.group(2))
            continue
        failed_match = re.search(r"(?i)measure\s+([A-Za-z_][A-Za-z0-9_.-]*)\s+failed", line)
        if failed_match:
            failed.append(failed_match.group(1))
    return values, failed


def build_runtime_deck(case: dict[str, Any]) -> str:
    deck_text = case["deck"].read_text(encoding="utf-8", errors="replace")
    if any(RUNTIME_CONTROL.match(line) for line in deck_text.splitlines()):
        raise ValueError(
            "runtime assertion instrumentation requires a deck without an embedded .control block"
        )
    lines = deck_text.splitlines()
    terminal_end = next(
        (index for index in range(len(lines) - 1, -1, -1) if RUNTIME_DECK_END.match(lines[index])),
        None,
    )
    if terminal_end is not None:
        del lines[terminal_end]
    while lines and not lines[-1].strip():
        lines.pop()
    runtime_lines = lines + [
        "",
        "* TR-1um runtime assertions generated by run_analog_sim.py.",
        ".control",
        "run",
        "let __tr1um_assert_failed = 0",
    ]
    for assertion in case["assertions"]:
        allowed = assertion["allowed"]
        if allowed is None:
            raise ValueError(f"assertion {assertion['name']} has no resolved limit or margin")
        expression = assertion["expression"]
        measured_expression = (
            f"abs({expression})" if assertion["mode"] == "absolute" else expression
        )
        runtime_lines.extend(
            [
                f"let {assertion['runtime_vector']} = {measured_expression}",
                f"meas tran {assertion['runtime_measure']} max {assertion['runtime_vector']}",
                f"if {assertion['runtime_measure']} >= {float(allowed):.17g}",
                f"  echo \"ASSERT_FAIL {assertion['runtime_measure']}: {assertion['message']}\"",
                "  let __tr1um_assert_failed = 1",
                "end",
            ]
        )
    runtime_lines.extend(
        [
            "if __tr1um_assert_failed > 0",
            "  quit 1",
            "end",
            ".endc",
            ".end",
            "",
        ]
    )
    return "\n".join(runtime_lines)


def run_case(case: dict[str, Any], output_dir: Path, ngspice: str) -> dict[str, Any]:
    name = case["name"]
    runtime_deck = output_dir / f"{name}.runtime.cir"
    log_path = output_dir / f"{name}.log"
    try:
        runtime_deck.write_text(build_runtime_deck(case), encoding="utf-8")
    except (OSError, ValueError) as exc:
        return {
            "name": name,
            "stage": case["stage"],
            "deck": str(case["deck"]),
            "runtime_deck": str(runtime_deck.resolve()),
            "source_views": case["source_views"],
            "sweeps": case["sweeps"],
            "returncode": None,
            "measurements": [],
            "assertions": [],
            "errors": [f"cannot prepare runtime assertion deck: {exc}"],
            "status": "FAIL",
            "log": str(log_path.resolve()),
        }
    command = [ngspice, "-b", "-o", str(log_path), str(runtime_deck)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    text += "\n" + completed.stdout + "\n" + completed.stderr
    if not log_path.exists():
        log_path.write_text(text, encoding="utf-8")
    values, failed_measures = parse_measurements(text)
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(f"ngspice returned {completed.returncode}")
    if re.search(r"(?im)^\s*(?:error|fatal):", text):
        errors.append("ngspice reported an error")
    if failed_measures:
        errors.append(f"failed measurements: {sorted(set(failed_measures))}")
    runtime_failures = re.findall(
        r"(?im)^\s*ASSERT_FAIL\s+([A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*(.*?)\s*$",
        text,
    )
    if runtime_failures:
        errors.append(
            "ngspice runtime assertion failure(s): "
            + "; ".join(f"{measure}: {message}" for measure, message in runtime_failures)
        )
    checks: list[dict[str, Any]] = []
    for measure in case["measures"]:
        measure_name = measure["name"]
        value = values.get(measure_name.lower())
        check: dict[str, Any] = {
            "name": measure_name,
            "value": value,
            "min": measure.get("min"),
            "max": measure.get("max"),
        }
        if value is None:
            check["status"] = "FAIL"
            errors.append(f"missing measurement: {measure_name}")
        elif "min" in measure and value < measure["min"]:
            check["status"] = "FAIL"
            errors.append(f"{measure_name}={value} is below min {measure['min']}")
        elif "max" in measure and value > measure["max"]:
            check["status"] = "FAIL"
            errors.append(f"{measure_name}={value} is above max {measure['max']}")
        else:
            check["status"] = "PASS"
        checks.append(check)
    assertion_checks: list[dict[str, Any]] = []
    for assertion in case["assertions"]:
        assertion_name = assertion["name"]
        measure_name = assertion["measure"]
        runtime_measure = assertion["runtime_measure"]
        raw_value = values.get(runtime_measure.lower())
        declared_value = values.get(measure_name.lower())
        limit = assertion["limit"]
        allowed = assertion["allowed"]
        observed = None if raw_value is None else (
            abs(raw_value) if assertion["mode"] == "absolute" else raw_value
        )
        peak_current = None if raw_value is None else abs(raw_value)
        density_limit = assertion["density_limit"]
        required_width = (
            None
            if peak_current is None or density_limit is None
            else peak_current / density_limit
        )
        assertion_check = {
            "name": assertion_name,
            "target": assertion["target"],
            "measure": measure_name,
            "declared_measurement_value": declared_value,
            "runtime_measure": runtime_measure,
            "expression": assertion["expression"],
            "message": assertion["message"],
            "raw_value": raw_value,
            "value": observed,
            "limit_ref": assertion["limit_ref"],
            "max": limit,
            "allowed_max": allowed,
            "margin_fraction": assertion["margin_fraction"],
            "mode": assertion["mode"],
            "width_um": assertion["width_um"],
            "density_limit_ref": assertion["density_limit_ref"],
            "density_limit_a_per_um": density_limit,
            "required_width_um": required_width,
        }
        assertion_ok = True
        if raw_value is None:
            errors.append(
                f"missing runtime assertion measurement: {runtime_measure} ({assertion_name})"
            )
            assertion_ok = False
        elif limit is None or allowed is None:
            errors.append(f"assertion limit or margin is unavailable: {assertion_name}")
            assertion_ok = False
        elif observed >= allowed:
            errors.append(
                f"{assertion_name} observed={observed} meets/exceeds allowed={allowed} "
                f"({assertion['limit_ref']}={limit}, margin_fraction={assertion['margin_fraction']})"
            )
            assertion_ok = False
        if assertion["width_um"] is not None:
            density_name = (
                "J_max_step_coverage"
                if ".steps." in str(assertion["density_limit_ref"])
                else "J_current_density"
            )
            if density_limit is None:
                errors.append(f"current-width density limit is unavailable: {assertion_name}")
                assertion_ok = False
            elif required_width is not None and assertion["width_um"] < required_width:
                errors.append(
                    f"{assertion_name} width={assertion['width_um']} um is below "
                    f"I_peak/{density_name}={required_width} um "
                    f"({assertion['density_limit_ref']}={density_limit})"
                )
                assertion_ok = False
        assertion_check["status"] = "PASS" if assertion_ok else "FAIL"
        assertion_checks.append(assertion_check)
    return {
        "name": name,
        "stage": case["stage"],
        "deck": str(case["deck"]),
        "runtime_deck": str(runtime_deck.resolve()),
        "source_views": case["source_views"],
        "sweeps": case["sweeps"],
        "returncode": completed.returncode,
        "measurements": checks,
        "assertions": assertion_checks,
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
        "log": str(log_path.resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ngspice", default="ngspice")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    manifest = load(manifest_path)
    cases, errors, _limits = validate(manifest, manifest_path)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if shutil.which(args.ngspice) is None:
        errors.append(f"ngspice executable not found: {args.ngspice}")
    results: list[dict[str, Any]] = []
    if not errors:
        for case in cases:
            results.append(run_case(case, args.output_dir, args.ngspice))
    overall = "PASS" if not errors and results and all(item["status"] == "PASS" for item in results) else ("BLOCKED" if errors else "FAIL")
    limits_path = resolve(manifest_path.parent, manifest.get("electrical_limits"))
    report = {
        "status": overall,
        "manifest": str(manifest_path),
        "design": manifest.get("design"),
        "electrical_limits": str(limits_path) if limits_path else None,
        "required_sweep_axes": manifest.get("required_sweep_axes", list(SWEEP_AXES)),
        "errors": errors,
        "cases": results,
    }
    output = args.output_dir / "analog_sim.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
