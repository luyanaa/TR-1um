#!/usr/bin/env python3
"""Summarize a KLayout report and fail on selected unvisited items.

KLayout stores both errors and foundry-declared warnings in the same report
format. By default warning categories beginning with ``WAR`` are informational;
``--fail-warnings`` makes every unvisited report item fatal.  The latter is the
required mode for the official IP62 signoff because warnings such as WAR06
identify electrically floating source/gate geometry.
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fail-warnings",
        action="store_true",
        help="treat foundry WAR categories as failures too",
    )
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    text = args.report.read_text()
    failures: dict[str, int] = {}
    for item in re.findall(r"<item>(.*?)</item>", text, re.DOTALL):
        if "<visited>false</visited>" not in item:
            continue
        match = re.search(r"<category>(.*?)</category>", item, re.DOTALL)
        category = html.unescape(match.group(1).strip()) if match else "<uncategorized>"
        # The runset emits warning names as 'WAR06: ...'. Do not classify
        # those as hard DRC failures; all other unvisited items are failures.
        if not args.fail_warnings and re.match(r"^'?WAR\d*\s*:", category):
            continue
        failures[category] = failures.get(category, 0) + 1
    if failures:
        for category, count in sorted(failures.items()):
            print(f"{count} hard item(s): {category}")
        return 1
    qualification = "unvisited" if args.fail_warnings else "hard"
    print(f"OK: no {qualification} KLayout items in {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
