#!/usr/bin/env python3
"""Fail only on unvisited hard KLayout report items.

KLayout stores both errors and foundry-declared warnings in the same report
format. Warning categories beginning with ``WAR`` are informational for the
TR-1um MPW mask run; every other unvisited item remains a hard failure.
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
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
        if re.match(r"^'?WAR\d*\s*:", category):
            continue
        failures[category] = failures.get(category, 0) + 1
    if failures:
        for category, count in sorted(failures.items()):
            print(f"{count} hard item(s): {category}")
        return 1
    print(f"OK: no hard KLayout items in {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
