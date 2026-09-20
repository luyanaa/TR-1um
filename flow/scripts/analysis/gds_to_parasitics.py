#!/usr/bin/env python3
"""Run the standalone TR-1um GDS -> DEF -> parasitics flow.

This driver intentionally keeps extraction separate from the ordinary DRC/LVS
entry points.  It stages ``extraction.lvs`` beside a selected PDK technology
collateral, runs KLayout net-only extraction, then invokes the existing
engineering RC estimator and post-layout SPICE merger.

The result is not a foundry-qualified PEX deck.  KLayout owns physical device
connectivity; the DEF bridge owns projected route geometry; and
extract_tr1um_parasitics.py owns the explicit RC estimate.  A source SPICE
netlist and an Xschem symbol are optional audit inputs.  They are never used as
a silent replacement for physical GDS connectivity.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RUNSET = SCRIPT_DIR / "extraction.lvs"
DEFAULT_TECH_ROOT = ROOT / "libs.tech" / "klayout" / "tech"
EXTRACT_SCRIPT = SCRIPT_DIR / "extract_tr1um_parasitics.py"
MERGE_SCRIPT = SCRIPT_DIR / "build_postlayout_spice.py"


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"unable to read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return value


def _run(command: Sequence[str], *, cwd: Path, log: Path, label: str) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"\n$ {shlex.join([str(part) for part in command])}\n")
        stream.flush()
        completed = subprocess.run(
            [str(part) for part in command],
            cwd=cwd,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
    if completed.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {completed.returncode}; see {log}")


def _stage_tech(runset: Path, tech_root: Path, scratch: Path) -> Path:
    """Stage the extraction runset with relative PDK includes intact."""
    if not runset.is_file():
        raise SystemExit(f"extraction runset not found: {runset}")
    if not tech_root.is_dir():
        raise SystemExit(f"KLayout technology root not found: {tech_root}")

    staged_tech = scratch / "tech"
    staged_lvs = staged_tech / "lvs"
    staged_drc = staged_tech / "drc"
    staged_lvs.mkdir(parents=True, exist_ok=True)
    staged_drc.mkdir(parents=True, exist_ok=True)

    source_drc = tech_root / "drc"
    source_lvs = tech_root / "lvs"
    if not source_drc.is_dir() or not source_lvs.is_dir():
        raise SystemExit(f"expected tech/drc and tech/lvs below {tech_root}")

    # Copy only the small runset collateral; never write into the PDK tree.
    shutil.copytree(source_drc, staged_drc, dirs_exist_ok=True)
    shutil.copytree(source_lvs, staged_lvs, dirs_exist_ok=True)
    staged_runset = staged_lvs / "extraction.lvs"
    shutil.copy2(runset, staged_runset)
    return staged_runset


def _wrap_klayout(command: list[str], nix_shell: str | None) -> list[str]:
    if not nix_shell:
        return command
    return [nix_shell, "--run", shlex.join(command)]


def _logical_subckt_ports(text: str, top: str) -> list[str] | None:
    """Read the first matching SPICE .SUBCKT port list."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"(?i)^\s*\.subckt\s+(\S+)(?:\s+(.*?))?\s*$", line)
        if not match or match.group(1).lower() != top.lower():
            continue
        tokens = (match.group(2) or "").split()
        index += 1
        while index < len(lines) and lines[index].lstrip().startswith("+"):
            tokens.extend(lines[index].lstrip()[1:].split())
            index += 1
        return [token.lstrip("\\") for token in tokens]
    return None


def _xschem_pins(path: Path) -> list[str]:
    """Extract Xschem symbol pin names without requiring Xschem itself."""
    pins: list[str] = []
    pattern = re.compile(r"^B\s+.*?\{name=([^\s}]+)", re.MULTILINE)
    for match in pattern.finditer(path.read_text(encoding="utf-8")):
        pin = match.group(1).strip()
        if pin not in pins:
            pins.append(pin)
    return pins


def _normalise_pins(pins: list[str] | None) -> list[str] | None:
    if pins is None:
        return None
    return [pin.replace("\\", "") for pin in pins]


def _pin_set(pins: list[str] | None) -> set[str] | None:
    if pins is None:
        return None
    return {pin.replace("\\", "").casefold() for pin in pins}

def _audit_inputs(
    *,
    extracted: Path,
    top: str,
    source_spice: Path | None,
    xschem_sym: Path | None,
) -> dict[str, Any]:
    extracted_ports = _logical_subckt_ports(extracted.read_text(encoding="utf-8"), top)
    source_ports = None
    sym_pins = None
    warnings: list[str] = []

    if extracted_ports is None:
        warnings.append(f"KLayout extracted netlist has no .SUBCKT {top} header")
    if source_spice:
        source_ports = _logical_subckt_ports(source_spice.read_text(encoding="utf-8"), top)
        if source_ports is None:
            warnings.append(f"source SPICE has no .SUBCKT {top} header")
        elif extracted_ports is not None and _pin_set(source_ports) != _pin_set(extracted_ports):
            warnings.append(
                "source SPICE and physical KLayout top-port lists differ; "
                "the physical KLayout netlist remains authoritative"
            )
    if xschem_sym:
        sym_pins = _xschem_pins(xschem_sym)
        if extracted_ports is not None and _pin_set(sym_pins) != _pin_set(extracted_ports):
            warnings.append(
                "Xschem symbol and physical KLayout top-port sets differ; "
                "the symbol is retained for audit only"
            )

    return {
        "physical_klayout_ports": extracted_ports,
        "source_spice_ports": source_ports,
        "xschem_symbol_pins": sym_pins,
        "warnings": warnings,
    }


def _add_common_path_argument(parser: argparse.ArgumentParser, *names: str, **kwargs: Any) -> None:
    parser.add_argument(*names, type=_path, **kwargs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run standalone TR-1um GDS connectivity extraction and engineering parasitic generation."
    )
    _add_common_path_argument(parser, "--gds", required=True, help="input layout GDS")
    parser.add_argument("--top", required=True, help="top cell / top SPICE subcircuit name")
    _add_common_path_argument(
        parser,
        "--rc",
        required=True,
        help="explicit engineering RC estimate JSON; no foundry RC deck is assumed",
    )
    _add_common_path_argument(
        parser,
        "--output-dir",
        required=True,
        help="scratch/output directory; all generated files are written here",
    )
    _add_common_path_argument(
        parser,
        "--source-spice",
        "--spice",
        dest="source_spice",
        help="optional source/reference SPICE for pin audit and provenance",
    )
    _add_common_path_argument(
        parser,
        "--xschem-sym",
        "--sym",
        dest="xschem_sym",
        help="optional Xschem symbol for top-pin audit",
    )
    _add_common_path_argument(
        parser,
        "--reference-netlist",
        help="optional explicit merge reference; defaults to the fresh KLayout netlist",
    )
    parser.add_argument("--reference-top", help="reference netlist top; defaults to --top")
    _add_common_path_argument(
        parser,
        "--runset",
        default=DEFAULT_RUNSET,
        help="standalone extraction.lvs template",
    )
    _add_common_path_argument(
        parser,
        "--tech-root",
        default=DEFAULT_TECH_ROOT,
        help="KLayout technology root containing tech/drc and tech/lvs",
    )
    parser.add_argument("--klayout", default="klayout", help="KLayout executable")
    parser.add_argument(
        "--nix-shell",
        nargs="?",
        const="nix-shell",
        default=None,
        help="run KLayout through nix-shell; optionally provide its executable",
    )
    _add_common_path_argument(
        parser,
        "--nix-shell-cwd",
        help="working directory for nix-shell; defaults to the current directory",
    )
    parser.add_argument("--run-mode", choices=("deep", "flat"), default="deep")
    parser.add_argument("--allow-partial", action="store_true", help="allow incomplete post-layout merge")
    parser.add_argument("--python", default=sys.executable, help="Python used for analysis scripts")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gds = args.gds
    rc = args.rc
    output_dir = args.output_dir
    runset = args.runset
    tech_root = args.tech_root
    source_spice = args.source_spice
    xschem_sym = args.xschem_sym

    for required in (gds, rc):
        if not required.is_file():
            raise SystemExit(f"input file not found: {required}")
    if source_spice and not source_spice.is_file():
        raise SystemExit(f"source SPICE not found: {source_spice}")
    if xschem_sym and not xschem_sym.is_file():
        raise SystemExit(f"Xschem symbol not found: {xschem_sym}")

    output_dir.mkdir(parents=True, exist_ok=True)
    scratch = output_dir / ".extraction_lvs"
    scratch.mkdir(parents=True, exist_ok=True)
    staged_runset = _stage_tech(runset, tech_root, scratch)

    bridge_def = output_dir / f"{args.top}.gds_connectivity.def"
    bridge_manifest = output_dir / f"{args.top}.gds_connectivity.json"
    klayout_extracted = output_dir / f"{args.top}.klayout.extracted"
    klayout_report = output_dir / f"{args.top}.klayout.lvsdb"
    klayout_log = output_dir / "klayout_extraction.log"

    extraction_command = [
        args.klayout,
        "-b",
        "-zz",
        "-r",
        str(staged_runset),
        "-rd",
        f"input={gds}",
        "-rd",
        f"top_cell={args.top}",
        "-rd",
        "netlist_only=true",
        "-rd",
        f"run_mode={args.run_mode}",
        "-rd",
        f"extracted={klayout_extracted}",
        "-rd",
        f"report={klayout_report}",
        "-rd",
        f"bridge_def={bridge_def}",
        "-rd",
        f"bridge_manifest={bridge_manifest}",
        "-rd",
        f"runset_source={runset}",
        "-rd",
        "ignore_top_ports_mismatch=true",
    ]
    _run(
        _wrap_klayout(extraction_command, args.nix_shell),
        cwd=args.nix_shell_cwd or Path.cwd(),
        log=klayout_log,
        label="KLayout extraction",
    )

    spef = output_dir / f"{args.top}.parasitics.spef"
    interconnect = output_dir / f"{args.top}.interconnect.sp"
    parasitics = output_dir / f"{args.top}.parasitics.json"
    pex_log = output_dir / "parasitics_extraction.log"
    pex_command = [
        args.python,
        str(EXTRACT_SCRIPT),
        "--def",
        str(bridge_def),
        "--gds",
        str(gds),
        "--extracted",
        str(klayout_extracted),
        "--top",
        args.top,
        "--rc",
        str(rc),
        "--spef",
        str(spef),
        "--spice",
        str(interconnect),
        "--json",
        str(parasitics),
    ]
    _run(pex_command, cwd=ROOT, log=pex_log, label="TR-1um parasitic extraction")

    postlayout = output_dir / f"{args.top}.postlayout.sp"
    devices_spice = output_dir / f"{args.top}.devices.sp"
    devices_json = output_dir / f"{args.top}.devices.json"
    merge_manifest = output_dir / f"{args.top}.pex_manifest.json"
    merge_log = output_dir / "postlayout_merge.log"
    reference_netlist = args.reference_netlist or klayout_extracted
    reference_top = args.reference_top or args.top
    if not reference_netlist.is_file():
        raise SystemExit(f"merge reference netlist not found: {reference_netlist}")

    merge_command = [
        args.python,
        str(MERGE_SCRIPT),
        "--extracted",
        str(klayout_extracted),
        "--interconnect",
        str(interconnect),
        "--parasitics",
        str(parasitics),
        "--top",
        args.top,
        "--output",
        str(postlayout),
        "--devices-out",
        str(devices_spice),
        "--devices-json",
        str(devices_json),
        "--manifest",
        str(merge_manifest),
        "--reference-netlist",
        str(reference_netlist),
        "--reference-top",
        reference_top,
    ]
    if args.allow_partial:
        merge_command.append("--allow-partial")
    _run(merge_command, cwd=ROOT, log=merge_log, label="post-layout SPICE merge")

    audit = _audit_inputs(
        extracted=klayout_extracted,
        top=args.top,
        source_spice=source_spice,
        xschem_sym=xschem_sym,
    )
    bridge = _json(bridge_manifest)
    parasitic_ledger = _json(parasitics)
    merge = _json(merge_manifest)
    flow_manifest = {
        "schema": 1,
        "status": "engineering_estimate_not_foundry_qualified",
        "authority": {
            "physical_connectivity": "KLayout LVS LayoutVsSchematic polygons_of_net",
            "route_geometry": "DEF bridge projected from exact-net polygon bounding boxes",
            "parasitics": "extract_tr1um_parasitics.py",
            "postlayout_merge": "build_postlayout_spice.py",
        },
        "inputs": {
            "gds": str(gds),
            "top": args.top,
            "rc": str(rc),
            "source_spice": str(source_spice) if source_spice else None,
            "xschem_sym": str(xschem_sym) if xschem_sym else None,
            "runset": str(runset),
            "tech_root": str(tech_root),
            "reference_netlist_used": str(reference_netlist),
        },
        "outputs": {
            "bridge_def": str(bridge_def),
            "bridge_manifest": str(bridge_manifest),
            "klayout_extracted": str(klayout_extracted),
            "spef": str(spef),
            "interconnect_spice": str(interconnect),
            "parasitics_json": str(parasitics),
            "postlayout_spice": str(postlayout),
            "merge_manifest": str(merge_manifest),
            "klayout_log": str(klayout_log),
            "pex_log": str(pex_log),
            "merge_log": str(merge_log),
        },
        "audit": audit,
        "bridge_summary": {
            "net_count": bridge.get("net_count"),
            "polygon_count": bridge.get("polygon_count"),
            "pin_connection_records": bridge.get("pin_connection_records"),
        },
        "parasitic_summary": parasitic_ledger.get("topology", {}),
        "merge_summary": {
            "merge_status": merge.get("merge_status"),
            "reference_mapped_instances": merge.get("hierarchy", {}).get("reference_mapped_instances"),
            "unresolved_reference_instances": merge.get("hierarchy", {}).get("unresolved_reference_instances"),
        },
        "warnings": audit["warnings"],
    }
    flow_manifest_path = output_dir / f"{args.top}.extraction_flow.json"
    flow_manifest_path.write_text(json.dumps(flow_manifest, indent=2) + "\n", encoding="utf-8")
    print(f"extraction_flow: status=complete top={args.top}")
    print(f"extraction_flow_manifest: {flow_manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
