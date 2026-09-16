#!/usr/bin/env python3
"""Generate the strict (non-circular) LVS contract for the mixed counter.

Inputs:
  --powered-netlist   routed PNL Verilog (design intent from synthesis+PnR)
  --macro-cdl         analog macro CDL (independently qualified contract)
  --frame-extracted   SPICE extraction of the immutable OSS_FRAME GDS
  --physical-extracted SPICE extraction of the routed mixed GDS. Its
                      standard-cell subcircuits provide fixed library views and
                      pin order; the routed top/core topology is never copied.
  --diode-cdl         diode CDL for antenna cells in the powered PNL

The generated contract never copies the routed layout's topology: the digital
core instances are translated from the PNL Verilog, the standard-cell views are
reused only as fixed library definitions from the hierarchical extraction, the
analog macro comes from its CDL, and the frame subcircuits come from an
independent extraction of the immutable frame GDS.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

CORE_CELLS = ("NAND2", "NAND3", "XOR2", "XNOR2", "AND4_X1", "DFFR")
DIODE_CELLS = ("DIODE_N_X1",)


def circuits(text: str) -> dict[str, str]:
    return {
        m.group(1).upper(): m.group(0).strip()
        for m in re.finditer(r"(?ims)^\.subckt\s+(\S+).*?^\.ends(?:\s+\S+)?\s*$", text)
    }


def port_order(circuit: str) -> list[str]:
    header = re.search(r"(?im)^\.subckt\s+\S+\s*(.*)$", circuit)
    if header is None:
        raise ValueError("missing .SUBCKT header")
    return header.group(1).split()


def replace_port_order(circuit: str, ports: list[str]) -> str:
    return re.sub(
        r"(?im)^(\.subckt\s+\S+)\s+.*$",
        rf"\1 {' '.join(ports)}",
        circuit,
        count=1,
    )

def verilog_instances(text: str) -> list[tuple[str, str, dict[str, str]]]:
    result: list[tuple[str, str, dict[str, str]]] = []
    allowed = set(CORE_CELLS) | set(DIODE_CELLS) | {"CMC_S_NMOS_B_X1_Y1"}
    for cell, instance, args in re.findall(r"(?ms)^\s*(\w+)\s+(\S+)\s*\((.*?)\);", text):
        if cell not in allowed:
            continue
        named = dict(re.findall(r"\.([A-Za-z0-9_]+)\s*\(\s*([^()\s]+)\s*\)", args))
        result.append((cell, instance, named))
    digital = sum(cell in CORE_CELLS for cell, _, _ in result)
    macros = sum(cell == "CMC_S_NMOS_B_X1_Y1" for cell, _, _ in result)
    if digital != 12 or macros != 1:
        raise ValueError(
            f"expected 12 digital instances and 1 macro, found {digital} digital and {macros} macro"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--powered-netlist", required=True, type=Path)
    parser.add_argument("--macro-cdl", required=True, type=Path)
    parser.add_argument("--frame-extracted", required=True, type=Path)
    parser.add_argument("--physical-extracted", required=True, type=Path)
    parser.add_argument(
        "--diode-cdl",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "pdk_root/TR-1um/libs.ref/TR-1um_antenna/cdl/DIODE_N_X1.cdl",
        help="CDL view for diode cells present in the powered PNL",
    )
    parser.add_argument("--top", default="tr1um_mixed_counter")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    physical = circuits(args.physical_extracted.read_text())
    frame = circuits(args.frame_extracted.read_text())
    macro_cdl = circuits(args.macro_cdl.read_text())
    if "CMC_S_NMOS_B_X1_Y1" not in macro_cdl:
        raise SystemExit("macro CDL missing CMC_S_NMOS_B_X1_Y1")

    # Physical cell views are allowed only for the fixed standard-cell
    # definitions and pin order; the routed top/core circuits are not copied.
    missing_views = [c for c in CORE_CELLS if c not in physical]
    if missing_views:
        raise SystemExit(f"physical standard-cell views missing: {missing_views}")
    # Frame subcircuits from the framed-design extraction. The unbonded pad
    # pins are absorbed by KLayout's netlist purge, so the frame call shape
    # must come from the same extraction that the LVS will compare against.
    frame_cells = ["OSS_FRAME", "OSS_ESD_5V_ANA", "OSS_ESD_5V_VDD", "OSS_ESD_5V_VSS"]
    frame_leaves = ["OSS_NCH_ESD", "OSS_PCH_ESD"]
    missing_frame = [c for c in frame_cells + frame_leaves if c not in frame]
    if missing_frame:
        raise SystemExit(f"frame cells missing from extraction: {missing_frame}")
    frame_ports = port_order(frame["OSS_FRAME"])
    if set(frame_ports) != {"VDD", "VSS"}:
        raise SystemExit(f"unexpected OSS_FRAME ports: {frame_ports}")
    # The assembled frame extraction exposes only its two global power pins.
    frame["OSS_FRAME"] = replace_port_order(frame["OSS_FRAME"], ["VDD", "VSS"])

    instances = verilog_instances(args.powered_netlist.read_text())
    diode_cells = {cell for cell, _, _ in instances if cell in DIODE_CELLS}
    diode_cdl = circuits(args.diode_cdl.read_text()) if diode_cells else {}
    missing_diode_cdl = sorted(diode_cells - diode_cdl.keys())
    if missing_diode_cdl:
        raise SystemExit(f"diode CDL missing cells: {missing_diode_cdl}")

    core_lines = []
    macro_args = None
    for cell, instance, named in instances:
        nets: list[str] = []
        if cell in DIODE_CELLS:
            value = named.get("DIODE") or named.get("diode")
            if value is None:
                raise ValueError(f"{instance} ({cell}) has no DIODE connection")
            core_lines.append(f"X{instance} {value} VSS {cell}")
            continue
        if cell == "CMC_S_NMOS_B_X1_Y1":
            # The macro CDL is authoritative. Physical extraction can omit an
            # unconnected macro pin after netlist purging.
            order = port_order(macro_cdl["CMC_S_NMOS_B_X1_Y1"])
            for pin in order:
                if pin.upper() in {"GND", "VSS"}:
                    nets.append("VSS")
                    continue
                value = named.get(pin) or named.get(pin.upper()) or named.get(pin.lower())
                if value is None:
                    raise ValueError(f"macro instance {instance} has no {pin} connection")
                nets.append(value)
            macro_args = " ".join(nets)
            continue
        for pin in port_order(physical[cell]):
            if pin.lower() == "vdd":
                nets.append("VDD")
            elif pin.lower() in {"gnd", "vss"}:
                nets.append("VSS")
            else:
                value = named.get(pin) or named.get(pin.upper()) or named.get(pin.lower())
                if value is None:
                    raise ValueError(f"{instance} ({cell}) has no {pin} connection")
                nets.append(value)
        core_lines.append(f"X{instance} {' '.join(nets)} {cell}")

    if macro_args is None:
        raise ValueError("no macro instance found in PNL")

    core_block = ".SUBCKT tr1um_mixed_counter_core VSS VDD\n"

    core_block += f"XANA {macro_args} CMC_S_NMOS_B_X1_Y1\n"
    core_block += "\n".join(core_lines)
    core_block += "\n.ENDS tr1um_mixed_counter_core"

    top = (
        f".SUBCKT {args.top} VDD VSS\n"
        "XFRAME VDD VSS OSS_FRAME\n"
        "XCORE VSS VDD tr1um_mixed_counter_core\n"
        f".ENDS {args.top}"
    )
    body = [
        "* Generated strict mixed LVS contract; do not hand-edit.",
        top,
        core_block,
    ]
    body.extend(frame[name] for name in frame_cells + frame_leaves)
    body.extend(physical[name] for name in CORE_CELLS)
    body.append(macro_cdl["CMC_S_NMOS_B_X1_Y1"])
    body.extend(diode_cdl[name] for name in sorted(diode_cells))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(body) + "\n")
    print(f"wrote {args.output}")
if __name__ == "__main__":
    main()
