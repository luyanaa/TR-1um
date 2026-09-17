#!/usr/bin/env python3
"""Validate an analog signoff evidence manifest.

The manifest separates evidence inventory from release closure.  ``inventory``
mode checks the schema and records which evidence exists.  ``signoff`` mode
also requires every required analysis to be ``pass`` or explicitly
``not_applicable`` with a justification.  ``engineering_only``, ``not_run``,
``blocked``, and ``fail`` never pass the signoff gate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

STATUSES = {"pass", "engineering_only", "not_run", "not_applicable", "blocked", "fail"}
REQUIRED_STAGES = (
    "macro_qualification",
    "ota_handoff",
    "m3_rc_scope",
    "erc_electrical",
    "antenna",
    "sta_pvt",
    "pdn_emir",
    "post_layout_sim",
    "crosstalk",
    "latchup",
    "mismatch_overdesign",
    "esd",
    "capacitance",
)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read signoff manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"ERROR: signoff manifest must be a JSON object: {path}")
    return value


def resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def nonempty_strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def validate(path: Path, mode: str) -> dict[str, Any]:
    manifest = load(path)
    errors: list[str] = []
    blockers: list[str] = []
    base = path.parent

    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    design = manifest.get("design")
    if not isinstance(design, dict) or not isinstance(design.get("name"), str) or not design["name"]:
        errors.append("design.name must be a non-empty string")
        design = design if isinstance(design, dict) else {}

    artifacts = manifest.get("artifacts", {})
    artifact_report: dict[str, Any] = {}
    if not isinstance(artifacts, dict):
        errors.append("artifacts must be an object")
        artifacts = {}
    for name, value in artifacts.items():
        if not isinstance(value, dict):
            errors.append(f"artifacts.{name} must be an object")
            continue
        artifact_path = value.get("path")
        classification = value.get("classification")
        if not isinstance(artifact_path, str) or not artifact_path:
            errors.append(f"artifacts.{name}.path must be a non-empty path")
            continue
        if classification not in {"signoff", "engineering_only", "reference", "not_run"}:
            errors.append(
                f"artifacts.{name}.classification must be signoff, engineering_only, reference, or not_run"
            )
        resolved = resolve(base, artifact_path)
        exists = resolved.is_file() and resolved.stat().st_size > 0
        artifact_report[name] = {
            "path": str(resolved),
            "classification": classification,
            "exists_nonempty": exists,
        }
        if classification in {"signoff", "engineering_only"} and not exists:
            errors.append(f"missing non-empty artifact {name}: {resolved}")

    stages = manifest.get("stages")
    if not isinstance(stages, dict):
        errors.append("stages must be an object")
        stages = {}
    missing = [name for name in REQUIRED_STAGES if name not in stages]
    if missing:
        errors.append(f"missing required stages: {missing}")

    stage_report: dict[str, Any] = {}
    for name in REQUIRED_STAGES:
        stage = stages.get(name)
        if not isinstance(stage, dict):
            errors.append(f"stages.{name} must be an object")
            continue
        status = stage.get("status")
        if status not in STATUSES:
            errors.append(f"stages.{name}.status must be one of {sorted(STATUSES)}")
            status = "invalid"
        evidence = stage.get("evidence", [])
        if not nonempty_strings(evidence):
            if status in {"pass", "engineering_only"}:
                errors.append(f"stages.{name}.evidence must list non-empty paths for status {status}")
            evidence = []
        evidence_report = []
        for item in evidence:
            resolved = resolve(base, item)
            exists = resolved.is_file() and resolved.stat().st_size > 0
            evidence_report.append({"path": str(resolved), "exists_nonempty": exists})
            if not exists:
                errors.append(f"stages.{name} evidence is missing or empty: {resolved}")
        rationale = stage.get("rationale", "")
        if status in {"not_run", "blocked", "fail"} and not isinstance(rationale, str):
            errors.append(f"stages.{name}.rationale must explain status {status}")
            rationale = ""
        if status in {"not_run", "blocked", "fail"} and not str(rationale).strip():
            errors.append(f"stages.{name}.rationale is required for status {status}")
        if status == "not_applicable" and not isinstance(rationale, str):
            errors.append(f"stages.{name}.rationale must justify not_applicable")
            rationale = ""
        if status == "not_applicable" and not str(rationale).strip():
            errors.append(f"stages.{name}.rationale is required for not_applicable")
        limits = stage.get("limits", [])
        if status == "pass" and not nonempty_strings(limits):
            errors.append(f"stages.{name}.limits must state acceptance limits for pass")
        if mode == "signoff" and status not in {"pass", "not_applicable"}:
            blockers.append(f"{name}={status}: {rationale or 'no closure evidence'}")
        stage_report[name] = {
            "status": status,
            "evidence": evidence_report,
            "limits": limits,
            "rationale": rationale,
        }

    if mode == "signoff" and manifest.get("release_status") != "ready":
        blockers.append(
            f"release_status={manifest.get('release_status')!r}; set ready only after all required stages close"
        )

    result = "PASS" if not errors and not blockers else ("INVALID" if errors else "INCOMPLETE")
    return {
        "status": result,
        "mode": mode,
        "manifest": str(path.resolve()),
        "design": design,
        "release_status": manifest.get("release_status"),
        "artifacts": artifact_report,
        "stages": stage_report,
        "errors": errors,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--mode", choices=("inventory", "signoff"), default="inventory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = validate(args.manifest.resolve(), args.mode)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
