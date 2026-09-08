#!/usr/bin/env python3
"""Generate the strict (non-circular) LVS contract for the mixed counter.

Inputs:
  --powered-netlist   routed PNL Verilog (design intent from synthesis+PnR)
  --macro-cdl         analog macro CDL (independently qualified contract)
  --frame-extracted   SPICE extraction of the immutable OSS_FRAME GDS
  --physical-extracted SPICE extraction of the routed mixed GDS (pin ORDER only)
  --output            contract .cir

The generated contract never copies the routed layout's topology: the digital
core instances are translated from the PNL Verilog connections, the analog
macro comes from its CDL, and the frame subcircuits come from an independent
extraction of the immutable frame GDS. The routed design's extraction is used
ONLY to obtain the physical pin order of the standard cells.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

CORE_CELLS = ("NAND2", "NAND3", "XOR2", "XNOR2", "AND4_X1", "DFFR")


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


def verilog_instances(text: str) -> list[tuple[str, str, dict[str, str]]]:
    result: list[tuple[str, str, dict[str, str]]] = []
    for cell, instance, args in re.findall(r"(?ms)^\s*(\w+)\s+(\S+)\s*\((.*?)\);", text):
        if cell not in CORE_CELLS and cell != "CMC_S_NMOS_B_X1_Y1":
            continue
        named = dict(re.findall(r"\.([A-Za-z0-9_]+)\s*\(\s*([^()\s]+)\s*\)", args))
        result.append((cell, instance, named))
    if len(result) != 13:
        raise ValueError(f"expected 13 instances (12 digital + 1 macro), found {len(result)}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--powered-netlist", required=True, type=Path)
    parser.add_argument("--macro-cdl", required=True, type=Path)
    parser.add_argument("--frame-extracted", required=True, type=Path)
    parser.add_argument("--physical-extracted", required=True, type=Path)
    parser.add_argument("--top", default="tr1um_mixed_counter")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    physical = circuits(args.physical_extracted.read_text())
    frame = circuits(args.frame_extracted.read_text())

    # Physical pin orders (order-only use of the routed extraction).
    missing = [c for c in CORE_CELLS if c not in physical]
    if missing:
        raise SystemExit(f"physical pin orders missing: {missing}")
    macro_physical = physical.get("CMC_S_NMOS_B_X1_Y1")

    # Frame subcircuits from the framed-design extraction. The unbonded pad
    # pins are absorbed by KLayout's netlist purge, so the frame call shape
    # must come from the same extraction that the LVS will compare against.
    frame_cells = ["OSS_FRAME", "OSS_ESD_5V_ANA", "OSS_ESD_5V_VDD", "OSS_ESD_5V_VSS"]
    frame_leaves = ["OSS_NCH_ESD", "OSS_PCH_ESD"]
    missing_frame = [c for c in frame_cells + frame_leaves if c not in frame]
    if missing_frame:
        raise SystemExit(f"frame cells missing from extraction: {missing_frame}")

    instances = verilog_instances(args.powered_netlist.read_text())

    core_lines = []
    macro_args = None
    for cell, instance, named in instances:
        nets: list[str] = []
        if cell == "CMC_S_NMOS_B_X1_Y1":
            # Macro pin order from the physical extraction, mapping from the
            # PNL named connections.
            order = port_order(macro_physical) if macro_physical else ["G", "DA", "SA", "DB", "SB", "GND"]
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

    macro_cdl = circuits(args.macro_cdl.read_text())
    if "CMC_S_NMOS_B_X1_Y1" not in macro_cdl:
        raise SystemExit("macro CDL missing CMC_S_NMOS_B_X1_Y1")

    core_block = ".SUBCKT tr1um_mixed_counter_core VSS VDD\n"
    core_block += f"XANA {macro_args} CMC_S_NMOS_B_X1_Y1\n"
    core_block += "\n".join(core_lines)
    core_block += "\n.ENDS tr1um_mixed_counter_core"

    top = (
        f".SUBCKT {args.top} VSS VDD\n"
        "XFRAME VSS VDD OSS_FRAME\n"
        "XCORE VSS VDD tr1um_mixed_counter_core\n"
        f".ENDS {args.top}"
    )

    body = [
        "* Generated strict mixed LVS contract; do not hand-edit.",
        top,
        core_block,
    ]
    body.extend(frame[name] for name in frame_cells + frame_leaves)
    body.append(macro_cdl["CMC_S_NMOS_B_X1_Y1"])
    body.extend(physical[name] for name in CORE_CELLS)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(body) + "\n")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
