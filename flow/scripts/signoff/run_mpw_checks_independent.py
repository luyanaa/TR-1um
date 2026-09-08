#!/usr/bin/env python3
"""Run the MPW frame pre-check, drawing DRC, MDP export, and mask DRC."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
gds = Path(os.environ["TR1UM_FRAMED_GDS"]).resolve()
top = os.environ.get("TR1UM_FRAMED_TOP", "tr_1um_counter")
klayout = os.environ.get("KLAYOUT_BIN", "klayout")
mpw = Path(os.environ.get("MPW_TEMPLATE", str(Path.home() / "Documents/TR-1um_MPW_template")))
out = Path(os.environ.get("TR1UM_MPW_REPORT", str(root / "flow/signoff/mpw-canonical")))
out.mkdir(parents=True, exist_ok=True)

# Run the structural check in KLayout's Python runtime. The template script
# imports Click, which is not available in every KLayout embedding, while pya
# is authoritative for the actual layout object.
subprocess.run([
    klayout,
    "-b",
    "-r",
    str(root / "flow/scripts/signoff/mpw_precheck_klayout.py"),
    "-rd",
    f"input={gds}",
    "-rd",
    f"top_cell={top}",
], check=True)

runsets = [
    ("drc", root / "libs.tech/klayout/tech/drc/run.drc", "drc.lyrdb"),
    ("ip62", root / "libs.tech/klayout/tech/drc/run_IP62.drc", "ip62.lyrdb"),
]
for name, runset, report in runsets:
    subprocess.run([
        klayout,
        "-b",
        "-zz",
        "-r",
        str(runset),
        "-rd",
        f"input={gds}",
        "-rd",
        f"top_cell={top}",
        "-rd",
        f"report={out / report}",
    ], check=True)
    subprocess.run([
        "python3",
        str(root / "flow/scripts/signoff/check_klayout_report.py"),
        str(out / report),
    ], check=True)
    print(name, out / report)

mdp = out / f"{top}_mdp.gds"
subprocess.run([
    klayout,
    "-b",
    "-zz",
    "-r",
    str(root / "libs.tech/klayout/tech/drc/run_mdp.drc"),
    "-rd",
    f"input={gds}",
    "-rd",
    f"top_cell={top}",
    "-rd",
    f"output={mdp}",
], check=True)
if not mdp.stat().st_size:
    raise RuntimeError("empty MDP GDS")
print("mdp", mdp)
