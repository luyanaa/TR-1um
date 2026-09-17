#!/usr/bin/env python3
"""Run LVS/DRC source parity, MPW pre-check, drawing DRC, MDP export, and mask DRC."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
gds = Path(os.environ["TR1UM_FRAMED_GDS"]).resolve()
top = os.environ.get("TR1UM_FRAMED_TOP", "tr_1um_counter")
klayout = os.environ.get("KLAYOUT_BIN", "klayout")
mpw = Path(os.environ.get("MPW_TEMPLATE", str(root / "TR-1um_MPW_template")))
pre_check = mpw / "scripts/pre_check.py"
parity_checker = root / "flow/scripts/signoff/check_drc_rule_parity.py"
lvs_parity_checker = root / "flow/scripts/signoff/check_lvs_source_parity.py"
parity_manifest = Path(
    os.environ.get(
        "DRC_RULE_PARITY_MANIFEST",
        str(root / "flow/qualification/drc_rule_parity.json"),
    )
).resolve()
lvs_parity_manifest = Path(
    os.environ.get(
        "LVS_SOURCE_PARITY_MANIFEST",
        str(root / "flow/qualification/lvs_source_parity.json"),
    )
).resolve()
lvs_runset = Path(
    os.environ.get(
        "LVS_RUNSET",
        str(root / "libs.tech/klayout/tech/lvs/run.lvs"),
    )
).resolve()
if not parity_checker.is_file():
    raise FileNotFoundError(f"DRC rule parity checker missing: {parity_checker}")
if not parity_manifest.is_file():
    raise FileNotFoundError(f"DRC rule parity manifest missing: {parity_manifest}")
if not lvs_parity_checker.is_file():
    raise FileNotFoundError(f"LVS source parity checker missing: {lvs_parity_checker}")
if not lvs_parity_manifest.is_file():
    raise FileNotFoundError(
        f"LVS source parity manifest missing: {lvs_parity_manifest}"
    )
if not lvs_runset.is_file():
    raise FileNotFoundError(f"LVS runset missing: {lvs_runset}")

out = Path(os.environ.get("TR1UM_MPW_REPORT", str(root / "flow/signoff/mpw-canonical")))
out.mkdir(parents=True, exist_ok=True)
drc_runset = root / "libs.tech/klayout/tech/drc/run.drc"
subprocess.run([
    "python3",
    str(lvs_parity_checker),
    "--manifest",
    str(lvs_parity_manifest),
    "--runset",
    str(lvs_runset),
    "--output",
    str(out / "lvs_source_parity.json"),
], check=True)
subprocess.run([
    "python3",
    str(parity_checker),
    "--manifest",
    str(parity_manifest),
    "--runset",
    str(drc_runset),
    "--output",
    str(out / "drc_rule_parity.json"),
], check=True)
if not pre_check.is_file():
    raise FileNotFoundError(
        f"MPW template pre-check missing: {pre_check}; "
        "initialize the TR-1um_MPW_template submodule or set MPW_TEMPLATE"
    )

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
    ("drc", drc_runset, "drc.lyrdb"),
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
