#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / "flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell_access"
DRC = ROOT / "libs.tech/klayout/tech/drc/run.drc"
LVS = ROOT / "libs.tech/klayout/tech/lvs/run.lvs"
QUAL = ROOT / "flow/qualification/ip62_beol"


def report_items(path: Path) -> list[str]:
    root = ET.parse(path).getroot()
    return [
        (item.findtext("category") or "").strip("'")
        for item in root.iter("item")
    ]


def main() -> None:
    gds_dir = LIB / "flow_gds"
    if not gds_dir.exists():
        raise SystemExit("derived library is absent; run build_ip62_access_library.sh")
    drc_dir = QUAL / "drc"
    lvs_dir = QUAL / "lvs"
    drc_dir.mkdir(parents=True, exist_ok=True)
    lvs_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    for gds in sorted(gds_dir.glob("*.gds")):
        name = gds.stem
        drc = drc_dir / f"{name}.lyrdb"
        result = subprocess.run(
            ["klayout", "-b", "-r", str(DRC), "-rd", f"input={gds}", "-rd", f"report={drc}"]
        )
        items = report_items(drc) if drc.exists() else ["missing DRC report"]
        if result.returncode or items:
            failures.append(f"{name}: DRC failed ({items})")

        lvs = lvs_dir / f"{name}.lvsdb"
        circuit = ROOT / "STDLIB/LogicCells/extracted" / f"{name}.extracted"
        result = subprocess.run(
            ["klayout", "-b", "-zz", "-r", str(LVS), "-rd", f"input={gds}", "-rd", f"top_cell={name}", "-rd", f"circuit={circuit}", "-rd", f"report={lvs}"],
            capture_output=True,
            text=True,
        )
        if result.returncode or "Netlists match" not in result.stdout:
            failures.append(f"{name}: LVS failed")
        print(f"{name}: {'PASS' if not any(f.startswith(name + ':') for f in failures) else 'FAIL'}")
    if failures:
        raise SystemExit("\n".join(failures))
    manifest = LIB / "access_manifest.json"
    if manifest.is_file():
        data = __import__("json").loads(manifest.read_text())
        data["status"] = "qualified_cell_views_pending_top_level_route"
        manifest.write_text(__import__("json").dumps(data, indent=2) + "\n")
    print(f"derived IP62 DRC/LVS qualification PASS: {len(list(gds_dir.glob('*.gds')))} cells")


if __name__ == "__main__":
    main()
