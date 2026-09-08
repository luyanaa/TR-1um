#!/usr/bin/env python3
"""Generate the independent strict LVS circuit for the framed counter.

Inputs are the routed powered Verilog netlist and the MPW frame's physical
netlist interface extracted once from the immutable GDS.  The generator never
copies the routed core topology from an extraction: it translates named
Verilog cell connections into the physical cell-pin order declared by the
physical cell contracts.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
FRAME_LEAF_CELLS = ("OSS_NCH_ESD", "OSS_PCH_ESD")
CORE_CELLS = ("NAND2", "NAND3", "XOR2", "XNOR2", "AND4_X1", "DFFR")
FRAME_CELLS = ("OSS_FRAME", "OSS_ESD_5V_ANA", "OSS_ESD_5V_VDD", "OSS_ESD_5V_VSS")


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
        if cell not in CORE_CELLS:
            continue
        named = dict(re.findall(r"\.([A-Za-z0-9_]+)\s*\(\s*([^()\s]+)\s*\)", args))
        result.append((cell, instance, named))
    if len(result) != 12:
        raise ValueError(f"expected 12 powered core instances, found {len(result)}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--physical-extracted", required=True, type=Path)
    parser.add_argument("--powered-netlist", required=True, type=Path)
    parser.add_argument("--top", default="tr_1um_counter")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    physical = circuits(args.physical_extracted.read_text())
    required = set(CORE_CELLS) | set(FRAME_CELLS) | set(FRAME_LEAF_CELLS)
    missing = required - physical.keys()
    if missing:
        raise SystemExit(f"physical contracts missing: {sorted(missing)}")

    core_lines = [".SUBCKT tr1um_counter_core VDD VSS"]
    for cell, instance, named in verilog_instances(args.powered_netlist.read_text()):
        nets: list[str] = []
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
    core_lines.append(".ENDS tr1um_counter_core")

    # The physical top exposes VSS/VDD only; KLayout preserves the unbonded
    # OSS_FRAME pad terminals internally when it extracts hierarchy.
    top = f".SUBCKT {args.top} VSS VDD\nXFRAME VSS VDD OSS_FRAME\nXCORE VDD VSS tr1um_counter_core\n.ENDS {args.top}"
    body = ["* Generated strict LVS contract; do not hand-edit.", top, "\n".join(core_lines)]
    body.extend(physical[name] for name in FRAME_CELLS + FRAME_LEAF_CELLS)
    body.extend(physical[name] for name in CORE_CELLS)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(body) + "\n")
if __name__ == "__main__":
    main()
