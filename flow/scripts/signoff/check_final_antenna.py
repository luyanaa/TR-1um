#!/usr/bin/env python3
"""Check antenna evidence at framed GDS, post-MDP GDS, and routed ODB stages."""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any


def klayout_categories(path: Path) -> Counter[str]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise SystemExit(f"ERROR: invalid KLayout report {path}: {exc}") from exc
    categories: Counter[str] = Counter()
    for item in root.iter("item"):
        categories[(item.findtext("category") or "<uncategorized>").strip("'")] += 1
    return categories


def antenna_items(categories: Counter[str]) -> dict[str, int]:
    return {
        category: count
        for category, count in categories.items()
        if re.search(r"antenna|\bANT\b", category, re.IGNORECASE)
    }


def openroad_counts(path: Path) -> dict[str, int]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SystemExit(f"ERROR: cannot read OpenROAD antenna report {path}: {exc}") from exc
    result: dict[str, int] = {}
    for key, label in (("net_violations", "net"), ("pin_violations", "pin")):
        match = re.search(rf"Found\s+(\d+)\s+{label}\s+violations?\.", text, re.IGNORECASE)
        if match is None:
            raise SystemExit(f"ERROR: OpenROAD antenna report lacks {label} violation count: {path}")
        result[key] = int(match.group(1))
    return result


def require_ruleset(path: Path, token: str | None = None) -> list[str]:
    if not path.is_file():
        return [f"missing antenna ruleset: {path}"]
    if token is not None and token not in path.read_text(encoding="utf-8", errors="replace"):
        return [f"antenna ruleset lacks {token}: {path}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framed-report", required=True, type=Path)
    parser.add_argument("--post-mdp-report", required=True, type=Path)
    parser.add_argument("--openroad-report", required=True, type=Path)
    parser.add_argument("--framed-ruleset", required=True, type=Path)
    parser.add_argument("--post-mdp-ruleset", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    errors = require_ruleset(args.framed_ruleset.resolve(), "GC.ANT")
    errors.extend(require_ruleset(args.post_mdp_ruleset.resolve()))
    framed = klayout_categories(args.framed_report.resolve())
    post_mdp = klayout_categories(args.post_mdp_report.resolve())
    framed_antenna = antenna_items(framed)
    post_mdp_antenna = antenna_items(post_mdp)
    if framed_antenna:
        errors.append(f"framed GDS antenna items: {framed_antenna}")
    if post_mdp_antenna:
        errors.append(f"post-MDP antenna items: {post_mdp_antenna}")
    openroad = openroad_counts(args.openroad_report.resolve())
    if any(value != 0 for value in openroad.values()):
        errors.append(f"OpenROAD antenna violations are nonzero: {openroad}")

    result: dict[str, Any] = {
        "status": "PASS" if not errors else "FAIL",
        "framed_report": str(args.framed_report.resolve()),
        "post_mdp_report": str(args.post_mdp_report.resolve()),
        "openroad_report": str(args.openroad_report.resolve()),
        "framed_categories": dict(sorted(framed.items())),
        "post_mdp_categories": dict(sorted(post_mdp.items())),
        "framed_antenna_items": framed_antenna,
        "post_mdp_antenna_items": post_mdp_antenna,
        "openroad_counts": openroad,
        "errors": errors,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
