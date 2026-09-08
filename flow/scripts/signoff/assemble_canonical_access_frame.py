#!/usr/bin/env python3
from pathlib import Path
import os, shutil, subprocess, sys

root = Path(__file__).resolve().parents[3]
def repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path

frame = repo_path(os.environ.get(
    "TR1UM_FRAME_GDS",
    "/Users/yanlu/Documents/TR-1um/libs.tech/klayout/libraries/TR-1um_frame_25x25.gds",
))
core = repo_path(os.environ.get(
    "TR1UM_CORE_GDS",
    "flow/designs/tr1um_counter/runs/access-canonical-final/51-klayout-streamout/tr1um_counter.klayout.gds",
))
out = repo_path(os.environ.get("TR1UM_FRAMED_GDS", "flow/signoff/tr_1um_counter_access_canonical.gds"))
top = os.environ.get("TR1UM_FRAMED_TOP", "tr_1um_counter")
klayout = os.environ.get("KLAYOUT_BIN") or shutil.which("klayout")
if not klayout:
    raise SystemExit("KLAYOUT_BIN or klayout is required")

env = {
    **os.environ,
    "TR1UM_FRAME_GDS": str(frame),
    "TR1UM_CORE_GDS": str(core),
    "TR1UM_FRAMED_GDS": str(out),
    "TR1UM_FRAMED_TOP": top,
}
subprocess.run([
    klayout,
    "-b",
    "-r",
    str(root / "flow/scripts/signoff/assemble_mpw_frame.py"),
], env=env, check=True)

# The framed GDS and its strict physical-contract schematic are one signoff
# artifact. Extract the physical hierarchy with KLayout, then regenerate the
# checked-in contract from that extraction and the powered routed netlist.
contract_dir = repo_path(os.environ.get("TR1UM_LVS_CONTRACT_DIR", "/tmp/tr1um-strict-lvs-contract"))
contract_dir.mkdir(parents=True, exist_ok=True)
physical = contract_dir / "physical.extracted"
report = contract_dir / "extraction.lvsdb"
runset = root / "libs.tech/klayout/tech/lvs/run.lvs"
subprocess.run([
    klayout,
    "-b",
    "-zz",
    "-r",
    str(runset),
    "-rd",
    f"input={out.resolve()}",
    "-rd",
    f"top_cell={top}",
    "-rd",
    "netlist_only=true",
    "-rd",
    f"extracted={physical}",
    "-rd",
    f"report={report}",
], check=True)

powered_netlist = repo_path(os.environ.get(
    "TR1UM_POWERED_NETLIST",
    "flow/designs/tr1um_counter/runs/access-canonical-final/final/pnl/tr1um_counter.pnl.v",
))
contract = repo_path(os.environ.get("TR1UM_LVS_CONTRACT", "flow/signoff/tr1um_counter.cir"))
subprocess.run([
    sys.executable,
    str(root / "flow/scripts/signoff/build_strict_lvs_contract.py"),
    "--physical-extracted",
    str(physical),
    "--powered-netlist",
    str(powered_netlist),
    "--top",
    top,
    "--output",
    str(contract),
], check=True)
print(out)
print(contract)
