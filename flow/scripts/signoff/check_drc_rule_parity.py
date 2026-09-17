#!/usr/bin/env python3
"""Check drawing-DRC source rows against generated runset rule IDs.

The checker is intentionally source-aware: a missing source rule must either
be present in the generated runset or carry an explicit, evidenced disposition.
Blocking dispositions keep unresolved or required rules from being mistaken for
covered checks; accepted dispositions remain visible as warnings.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DISPOSITION_STATUSES = {
    "required",
    "covered_by_alias",
    "obsolete",
    "unknown",
    "not_implemented",
    "advisory_only",
    "fab_accepted",
}
TODO_DISPOSITION_STATUSES = {"required", "unknown", "not_implemented"}
ACCEPTED_DISPOSITION_STATUSES = {
    "covered_by_alias",
    "obsolete",
    "advisory_only",
    "fab_accepted",
}
OUTPUT_RE = re.compile(r"\.output\(\s*(['\"])(.*?)\1", re.DOTALL)
RULE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read parity manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"parity manifest must be a JSON object: {path}")
    return value


def resolve_file(base: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        errors.append(f"{label} must be a non-empty path")
        return None
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    if not path.is_file():
        errors.append(f"{label} does not exist: {path}")
        return None
    return path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_source(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rules: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    try:
        with path.open(newline="", encoding="utf-8") as csv_file:
            rows = csv.reader(csv_file)
            for line_number, row in enumerate(rows, start=1):
                if not row or row[0].strip() in {"", "#", "Rule"}:
                    continue
                if len(row) < 6:
                    errors.append(
                        f"CSV line {line_number}: expected at least 6 columns, got {len(row)}"
                    )
                    continue
                rule = row[0].replace(" ", "")
                if not rule:
                    errors.append(f"CSV line {line_number}: rule ID is empty")
                    continue
                if rule in seen:
                    errors.append(f"CSV line {line_number}: duplicate rule ID {rule}")
                    continue
                seen.add(rule)

                unresolved = [
                    field
                    for field, value in zip(("MIN", "MAX"), row[4:6])
                    if value.strip() == "???"
                ]
                numeric_errors: list[str] = []
                for field, value in zip(("MIN", "MAX"), row[4:6]):
                    if value.strip() in {"", "???"}:
                        continue
                    try:
                        float(value)
                    except ValueError:
                        numeric_errors.append(field)
                if numeric_errors:
                    errors.append(
                        f"CSV line {line_number} ({rule}): nonnumeric {', '.join(numeric_errors)}"
                    )

                rules.append(
                    {
                        "rule": rule,
                        "source_line": line_number,
                        "l1": row[1].strip(),
                        "l2": row[2].strip(),
                        "func": row[3].strip(),
                        "min": row[4].strip(),
                        "max": row[5].strip(),
                        "unresolved": unresolved,
                    }
                )
    except OSError as exc:
        errors.append(f"cannot read source CSV {path}: {exc}")
    return rules, errors


def parse_runset(path: Path) -> tuple[set[str], list[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return set(), [f"cannot read generated runset {path}: {exc}"]

    categories = [match.group(2).strip() for match in OUTPUT_RE.finditer(text)]
    rule_ids = {
        category.split(":", 1)[0].strip()
        for category in categories
        if category and RULE_ID_RE.fullmatch(category.split(":", 1)[0].strip())
    }
    return rule_ids, []


def validate_reference(
    base: Path, reference: Any, label: str, errors: list[str]
) -> None:
    if isinstance(reference, str):
        path_value = reference
        line_value = None
    elif isinstance(reference, dict):
        path_value = reference.get("path")
        line_value = reference.get("line")
    else:
        errors.append(f"{label} must be a path string or object")
        return

    path = resolve_file(base, path_value, label, errors)
    if line_value is not None and (
        not isinstance(line_value, int) or isinstance(line_value, bool) or line_value < 1
    ):
        errors.append(f"{label}.line must be a positive integer")
    if path is not None and line_value is not None:
        try:
            line_count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError as exc:
            errors.append(f"{label}: cannot read {path}: {exc}")
        else:
            if line_value > line_count:
                errors.append(f"{label}.line {line_value} exceeds {path} ({line_count} lines)")


def validate_disposition(
    base: Path, rule: str, value: Any, errors: list[str]
) -> str | None:
    label = f"dispositions.{rule}"
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return None

    status = value.get("status")
    if status not in DISPOSITION_STATUSES:
        errors.append(
            f"{label}.status must be one of {sorted(DISPOSITION_STATUSES)}"
        )
    rationale = value.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        errors.append(f"{label}.rationale must be a non-empty string")
    if status == "fab_accepted" and value.get("acceptance_basis") != "fab":
        errors.append(f"{label}.acceptance_basis must be 'fab' for fab_accepted")

    references = value.get("references")
    if not isinstance(references, list) or not references:
        errors.append(f"{label}.references must be a non-empty list")
    else:
        for index, reference in enumerate(references):
            validate_reference(base, reference, f"{label}.references[{index}]", errors)

    if status == "covered_by_alias":
        aliases = value.get("covered_by")
        if not isinstance(aliases, list) or not aliases or not all(
            isinstance(alias, str) and alias.strip() for alias in aliases
        ):
            errors.append(f"{label}.covered_by must list non-empty alias rule IDs")

    return status if isinstance(status, str) else None


def check(
    manifest_path: Path,
    csv_override: Path | None = None,
    generator_override: Path | None = None,
    runset_override: Path | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    base = manifest_path.parent
    errors: list[str] = []
    todo_reasons: dict[str, list[str]] = {}
    warning_reasons: dict[str, list[str]] = {}

    try:
        manifest = load_manifest(manifest_path)
    except ValueError as exc:
        return {
            "status": "INVALID",
            "manifest": str(manifest_path),
            "errors": [str(exc)],
            "blockers": [],
        }

    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    design = manifest.get("design")
    if not isinstance(design, str) or not design.strip():
        errors.append("design must be a non-empty string")

    source = manifest.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
        source = {}
    path_base = Path.cwd()
    csv_path = resolve_file(
        path_base if csv_override else base,
        csv_override if csv_override else source.get("csv"),
        "source.csv",
        errors,
    )
    generator_path = resolve_file(
        path_base if generator_override else base,
        generator_override if generator_override else source.get("generator"),
        "source.generator",
        errors,
    )
    runset_path = resolve_file(
        path_base if runset_override else base,
        runset_override if runset_override else source.get("runset"),
        "source.runset",
        errors,
    )

    rules: list[dict[str, Any]] = []
    source_errors: list[str] = []
    if csv_path is not None:
        rules, source_errors = parse_source(csv_path)
        errors.extend(source_errors)

    runset_ids: set[str] = set()
    runset_errors: list[str] = []
    if runset_path is not None:
        runset_ids, runset_errors = parse_runset(runset_path)
        errors.extend(runset_errors)

    dispositions = manifest.get("dispositions")
    if not isinstance(dispositions, dict):
        errors.append("dispositions must be an object")
        dispositions = {}

    source_ids = {item["rule"] for item in rules}
    for rule in dispositions:
        if rule not in source_ids:
            errors.append(f"dispositions.{rule} is not present in source CSV")

    disposition_statuses: dict[str, str] = {}
    for rule, value in dispositions.items():
        status = validate_disposition(base, rule, value, errors)
        if status is not None:
            disposition_statuses[rule] = status

    missing_rules = [item for item in rules if item["rule"] not in runset_ids]
    unresolved_rules = [item for item in rules if item["unresolved"]]
    for item in missing_rules:
        rule = item["rule"]
        status = disposition_statuses.get(rule)
        if status is None:
            todo_reasons.setdefault(rule, []).append(
                "missing from generated runset and has no disposition"
            )
        elif status in TODO_DISPOSITION_STATUSES:
            todo_reasons.setdefault(rule, []).append(
                f"missing from generated runset with disposition {status}"
            )
        elif status in ACCEPTED_DISPOSITION_STATUSES:
            warning_reasons.setdefault(rule, []).append(
                f"missing from generated runset with disposition {status}"
            )

    for item in unresolved_rules:
        rule = item["rule"]
        status = disposition_statuses.get(rule)
        detail = f"unresolved source value(s) {item['unresolved']}"
        if status is None:
            todo_reasons.setdefault(rule, []).append(f"{detail}; no disposition")
        elif status in TODO_DISPOSITION_STATUSES:
            todo_reasons.setdefault(rule, []).append(
                f"{detail}; disposition {status}"
            )
        elif status in ACCEPTED_DISPOSITION_STATUSES:
            warning_reasons.setdefault(rule, []).append(
                f"{detail}; disposition {status}"
            )

    matched_ids = sorted(source_ids & runset_ids)
    extra_ids = sorted(runset_ids - source_ids)
    accepted = {
        rule: status
        for rule, status in disposition_statuses.items()
        if status in ACCEPTED_DISPOSITION_STATUSES
    }
    todos = [
        f"{rule}: {'; '.join(reasons)}"
        for rule, reasons in sorted(todo_reasons.items())
    ]
    warnings = [
        f"{rule}: {'; '.join(reasons)}"
        for rule, reasons in sorted(warning_reasons.items())
    ]

    status = "INVALID" if errors else ("PASS_WITH_WARNINGS" if todos or warnings else "PASS")
    todo_dispositions = {
        rule: status
        for rule, status in disposition_statuses.items()
        if status in TODO_DISPOSITION_STATUSES
    }
    result: dict[str, Any] = {
        "schema_version": manifest.get("schema_version"),
        "status": status,
        "manifest": str(manifest_path),
        "design": design,
        "source_csv": str(csv_path) if csv_path else None,
        "generator": str(generator_path) if generator_path else None,
        "generated_runset": str(runset_path) if runset_path else None,
        "source_csv_sha256": sha256(csv_path) if csv_path else None,
        "generated_runset_sha256": sha256(runset_path) if runset_path else None,
        "source_rule_count": len(rules),
        "generated_rule_id_count": len(runset_ids),
        "matched_rules": matched_ids,
        "missing_rules": [item["rule"] for item in missing_rules],
        "unresolved_rules": [
            {
                "rule": item["rule"],
                "source_line": item["source_line"],
                "values": item["unresolved"],
            }
            for item in unresolved_rules
        ],
        "accepted_dispositions": accepted,
        "todo_dispositions": todo_dispositions,
        "todos": todos,
        "warnings": warnings,
        "extra_generated_rule_ids": extra_ids,
        "errors": errors,
        "blockers": [],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--csv",
        dest="csv_override",
        type=Path,
        help="override source.csv; relative paths resolve from the current directory",
    )
    parser.add_argument(
        "--generator",
        dest="generator_override",
        type=Path,
        help="override source.generator; relative paths resolve from the current directory",
    )
    parser.add_argument(
        "--runset",
        dest="runset_override",
        type=Path,
        help="override source.runset; relative paths resolve from the current directory",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = check(
        args.manifest,
        csv_override=args.csv_override,
        generator_override=args.generator_override,
        runset_override=args.runset_override,
    )
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 2 if result["status"] == "INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
