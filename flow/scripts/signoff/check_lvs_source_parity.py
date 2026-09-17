#!/usr/bin/env python3
"""Check the active KLayout LVS source, runset, and tutorial inventory.

The checker proves the machine-readable inclusion graph and evidence references.
It does not infer semantic equivalence from prose: declared manual drift and
reference-only material remain visible warnings instead of being treated as
signoff coverage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CLAIM_STATUSES = {"covered", "drift", "reference_only", "excluded", "not_run"}
WARNING_CLAIM_STATUSES = {"drift", "reference_only", "not_run"}
INCLUDE_RE = re.compile(r"^\s*#\s+%include\s+(\S+)\s*$")
MARKDOWN_LINK_RE = re.compile(
    r"\]\(\s*(?:<(?P<bracket>[^>]+)>|(?P<bare>[^\s)]+))"
)
EXTERNAL_PREFIXES = (
    "http://",
    "https://",
    "ftp://",
    "mailto:",
    "data:",
)


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read LVS parity manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"LVS parity manifest must be a JSON object: {path}")
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


def parse_includes(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [], [f"cannot read LVS source {path}: {exc}"]

    for line_number, line in enumerate(lines, start=1):
        match = INCLUDE_RE.match(line)
        if not match:
            continue
        target = match.group(1)
        entries.append(
            {
                "from": str(path),
                "line": line_number,
                "target": target,
                "resolved": str((path.parent / target).resolve()),
            }
        )
    return entries, errors


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
            line_count = len(
                path.read_text(encoding="utf-8", errors="replace").splitlines()
            )
        except OSError as exc:
            errors.append(f"{label}: cannot read {path}: {exc}")
        else:
            if line_value > line_count:
                errors.append(
                    f"{label}.line {line_value} exceeds {path} ({line_count} lines)"
                )


def parse_manual_links(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    links: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [], [f"cannot read manual file {path}: {exc}"]

    for line_number, line in enumerate(lines, start=1):
        for match in MARKDOWN_LINK_RE.finditer(line):
            target = (match.group("bracket") or match.group("bare") or "").strip()
            if (
                not target
                or target.startswith("#")
                or target.startswith(EXTERNAL_PREFIXES)
                or target.startswith("/")
            ):
                continue
            target_path = target.split("#", 1)[0].split("?", 1)[0]
            if not target_path:
                continue
            resolved = (path.parent / target_path).resolve()
            links.append(
                {
                    "manual": str(path),
                    "line": line_number,
                    "target": target,
                    "resolved": str(resolved),
                    "exists": resolved.exists(),
                }
            )
    return links, errors


def deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def check(manifest_path: Path, runset_override: Path | None = None) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    base = manifest_path.parent
    errors: list[str] = []
    warnings: list[str] = []

    try:
        manifest = load_manifest(manifest_path)
    except ValueError as exc:
        return {
            "schema_version": None,
            "status": "INVALID",
            "manifest": str(manifest_path),
            "design": None,
            "errors": [str(exc)],
            "warnings": [],
            "blockers": [],
        }

    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    design = manifest.get("design")
    if not isinstance(design, str) or not design.strip():
        errors.append("design must be a non-empty string")

    active = manifest.get("active")
    if not isinstance(active, dict):
        errors.append("active must be an object")
        active = {}

    declared_runset = resolve_file(
        base, active.get("runset"), "active.runset", errors
    )
    checked_runset = resolve_file(
        Path.cwd() if runset_override else base,
        runset_override if runset_override else active.get("runset"),
        "checked runset",
        errors,
    )
    wrapper = resolve_file(base, active.get("wrapper"), "active.wrapper", errors)

    expected_includes_value = active.get("includes")
    expected_includes: list[str] = []
    if not isinstance(expected_includes_value, list) or not expected_includes_value:
        errors.append("active.includes must be a non-empty list")
    else:
        for index, value in enumerate(expected_includes_value):
            if not isinstance(value, str) or not value.strip():
                errors.append(f"active.includes[{index}] must be a non-empty string")
            else:
                expected_includes.append(value)
        if len(expected_includes) != len(set(expected_includes)):
            errors.append("active.includes must not contain duplicate paths")

    source_files_value = active.get("source_files")
    source_files: list[Path] = []
    if not isinstance(source_files_value, list) or not source_files_value:
        errors.append("active.source_files must be a non-empty list")
    else:
        for index, value in enumerate(source_files_value):
            path = resolve_file(base, value, f"active.source_files[{index}]", errors)
            if path is not None:
                source_files.append(path)
        if len(source_files) != len(set(source_files)):
            errors.append("active.source_files must not contain duplicate paths")

    include_entries: list[dict[str, Any]] = []
    if checked_runset is not None:
        include_entries, include_errors = parse_includes(checked_runset)
        errors.extend(include_errors)
        actual_includes = [entry["target"] for entry in include_entries]
        if actual_includes != expected_includes:
            errors.append(
                "active runset include order/content differs: "
                f"expected {expected_includes}, got {actual_includes}"
            )

        included_paths = [Path(entry["resolved"]) for entry in include_entries]
        for entry, path in zip(include_entries, included_paths):
            entry["exists"] = path.is_file()
            if not path.is_file():
                errors.append(
                    f"active include {entry['target']} at "
                    f"{entry['from']}:{entry['line']} does not exist: {path}"
                )
        if set(included_paths) != set(source_files):
            errors.append(
                "active.source_files differs from resolved runset includes: "
                f"declared {sorted(str(path) for path in source_files)}, "
                f"included {sorted(str(path) for path in included_paths)}"
            )

    wrapper_entries: list[dict[str, Any]] = []
    if wrapper is not None:
        wrapper_entries, wrapper_errors = parse_includes(wrapper)
        errors.extend(wrapper_errors)
        wrapper_includes = [entry["target"] for entry in wrapper_entries]
        if wrapper_includes != ["run.lvs"]:
            errors.append(
                "active.wrapper must contain exactly '# %include run.lvs': "
                f"got {wrapper_includes}"
            )
        if wrapper_entries and declared_runset is not None:
            wrapper_target = Path(wrapper_entries[0]["resolved"])
            if wrapper_target != declared_runset:
                errors.append(
                    "active.wrapper does not target active.runset: "
                    f"{wrapper_target} != {declared_runset}"
                )

    manual = manifest.get("manual")
    if not isinstance(manual, dict):
        errors.append("manual must be an object")
        manual = {}
    manual_files_value = manual.get("files")
    manual_files: list[Path] = []
    if not isinstance(manual_files_value, list) or not manual_files_value:
        errors.append("manual.files must be a non-empty list")
    else:
        for index, value in enumerate(manual_files_value):
            path = resolve_file(base, value, f"manual.files[{index}]", errors)
            if path is not None:
                manual_files.append(path)
        if len(manual_files) != len(set(manual_files)):
            errors.append("manual.files must not contain duplicate paths")

    manual_links: list[dict[str, Any]] = []
    for path in manual_files:
        links, link_errors = parse_manual_links(path)
        manual_links.extend(links)
        errors.extend(link_errors)
    for link in manual_links:
        if not link["exists"]:
            warnings.append(
                f"manual link {link['manual']}:{link['line']} -> "
                f"{link['target']} is missing ({link['resolved']})"
            )

    excluded = manifest.get("excluded")
    excluded_files: list[dict[str, Any]] = []
    if not isinstance(excluded, list):
        errors.append("excluded must be a list")
        excluded = []
    for index, entry in enumerate(excluded):
        label = f"excluded[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        path = resolve_file(base, entry.get("path"), f"{label}.path", errors)
        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{label}.reason must be a non-empty string")
        if path is not None:
            if path in source_files:
                errors.append(f"{label}.path is also an active source file: {path}")
            excluded_files.append(
                {
                    "path": str(path),
                    "sha256": sha256(path),
                    "reason": reason,
                }
            )

    claims = manifest.get("claims")
    normalized_claims: list[dict[str, Any]] = []
    claim_ids: set[str] = set()
    if not isinstance(claims, list) or not claims:
        errors.append("claims must be a non-empty list")
        claims = []
    for index, claim in enumerate(claims):
        label = f"claims[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{label} must be an object")
            continue
        claim_id = claim.get("id")
        if not isinstance(claim_id, str) or not claim_id.strip():
            errors.append(f"{label}.id must be a non-empty string")
            claim_id = f"<claim {index}>"
        elif claim_id in claim_ids:
            errors.append(f"duplicate claim id: {claim_id}")
        else:
            claim_ids.add(claim_id)
        status = claim.get("status")
        if status not in CLAIM_STATUSES:
            errors.append(
                f"{label}.status must be one of {sorted(CLAIM_STATUSES)}"
            )
        summary = claim.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            errors.append(f"{label}.summary must be a non-empty string")
            summary = ""
        rationale = claim.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"{label}.rationale must be a non-empty string")
            rationale = ""
        references = claim.get("references")
        if not isinstance(references, list) or not references:
            errors.append(f"{label}.references must be a non-empty list")
            references = []
        else:
            for ref_index, reference in enumerate(references):
                validate_reference(
                    base,
                    reference,
                    f"{label}.references[{ref_index}]",
                    errors,
                )
        normalized_claims.append(
            {
                "id": claim_id,
                "status": status,
                "summary": summary,
                "rationale": rationale,
                "references": references,
            }
        )
        if status in WARNING_CLAIM_STATUSES:
            warnings.append(f"{claim_id}: {status}: {summary}")

    warnings = deduplicate(warnings)
    errors = deduplicate(errors)
    status = "INVALID" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS")

    source_inventory: list[dict[str, Any]] = []
    include_lines_by_path: dict[str, list[int]] = {}
    for entry in include_entries:
        include_lines_by_path.setdefault(entry["resolved"], []).append(entry["line"])
    for path in source_files:
        source_inventory.append(
            {
                "path": str(path),
                "sha256": sha256(path),
                "include_lines": include_lines_by_path.get(str(path), []),
            }
        )

    result: dict[str, Any] = {
        "schema_version": manifest.get("schema_version"),
        "status": status,
        "manifest": str(manifest_path),
        "design": design,
        "active": {
            "wrapper": str(wrapper) if wrapper else None,
            "wrapper_sha256": sha256(wrapper) if wrapper else None,
            "runset": str(declared_runset) if declared_runset else None,
            "runset_sha256": sha256(declared_runset) if declared_runset else None,
            "checked_runset": str(checked_runset) if checked_runset else None,
            "checked_runset_sha256": sha256(checked_runset)
            if checked_runset
            else None,
            "expected_includes": expected_includes,
            "actual_includes": [entry["target"] for entry in include_entries],
            "wrapper_includes": [entry["target"] for entry in wrapper_entries],
            "include_graph": include_entries,
            "source_files": source_inventory,
        },
        "manual_files": [
            {"path": str(path), "sha256": sha256(path)} for path in manual_files
        ],
        "manual_links": manual_links,
        "broken_manual_links": [
            link for link in manual_links if not link["exists"]
        ],
        "excluded_files": excluded_files,
        "claims": normalized_claims,
        "warnings": warnings,
        "errors": errors,
        "blockers": [],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--runset",
        dest="runset_override",
        type=Path,
        help="override active.runset; relative paths resolve from the current directory",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = check(args.manifest, runset_override=args.runset_override)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 2 if result["status"] == "INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
