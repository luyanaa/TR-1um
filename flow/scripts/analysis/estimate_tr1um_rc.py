#!/usr/bin/env python3
"""Calculate the reproducible TR-1um digital interconnect RC estimate.

Tokai Rika's open IP62 reference manual explicitly lists no parasitic-extraction
collateral. This report therefore treats the values in the derived technology
LEF as engineering estimates, not foundry measurements. It derives the
per-unit-length values consumed by OpenROAD from:

    R' = R_sheet / width
    C' = C_area * width + 2 * C_edge

The uncertainty bands are deliberately explicit and are intended for timing
sensitivity analysis until silicon or foundry RC/PEX data are available.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DEFAULT_LEF = Path(__file__).resolve().parents[2] / "pdk_root/TR-1um/libs.ref/TR-1um_stdcell/lef/TR-1um_tech.lef"
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "pdk_root/TR-1um/libs.tech/librelane/rc_estimate.json"

# Engineering uncertainty, not a statistical confidence interval.
SHEET_R_SPREAD = 0.50
CAP_SPREAD = 0.50
VIA_R_NOMINAL_OHM = 1.0
VIA_R_LOW_OHM = 0.5
VIA_R_HIGH_OHM = 2.0
ACTIVE_ROUTING_LAYERS = ("M1", "M2")
# Access-cell technology LEFs intentionally expose only active M1/M2.  Full
# source/framed technology LEFs may additionally declare M3 for reserved-layer
# sensitivity reporting.
RESERVED_ROUTING_LAYERS = ("M3",)



def layer_block(text: str, layer: str) -> str:
    match = re.search(rf"(?ms)^LAYER {layer}\s*\n(.*?)^END {layer}\s*$", text)
    if not match:
        raise ValueError(f"missing routing layer {layer}")
    return match.group(1)


def value(block: str, key: str) -> float:
    match = re.search(rf"{key}\s+([0-9.eE+-]+)", block)
    if not match:
        raise ValueError(f"missing {key}")
    return float(match.group(1))


def estimate_layer(text: str, layer: str) -> dict[str, object]:
    block = layer_block(text, layer)
    width_um = value(block, "WIDTH")
    sheet_ohm_per_square = value(block, "RESISTANCE RPERSQ")
    area_pf_per_um2 = value(block, "CAPACITANCE CPERSQDIST")
    edge_pf_per_um = value(block, "EDGECAPACITANCE")
    resistance_ohm_per_um = sheet_ohm_per_square / width_um
    capacitance_pf_per_um = area_pf_per_um2 * width_um + 2.0 * edge_pf_per_um
    return {
        "layer": layer,
        "width_um": width_um,
        "sheet_resistance_ohm_per_square": sheet_ohm_per_square,
        "capacitance_area_pf_per_um2": area_pf_per_um2,
        "edge_capacitance_pf_per_um": edge_pf_per_um,
        "resistance_ohm_per_um": resistance_ohm_per_um,
        "capacitance_pf_per_um": capacitance_pf_per_um,
        "capacitance_ff_per_um": capacitance_pf_per_um * 1000.0,
        "resistance_range_ohm_per_um": [
            resistance_ohm_per_um * (1.0 - SHEET_R_SPREAD),
            resistance_ohm_per_um * (1.0 + SHEET_R_SPREAD),
        ],
        "capacitance_range_ff_per_um": [
            capacitance_pf_per_um * 1000.0 * (1.0 - CAP_SPREAD),
            capacitance_pf_per_um * 1000.0 * (1.0 + CAP_SPREAD),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lef", type=Path, default=DEFAULT_LEF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    text = args.lef.read_text(encoding="utf-8")

    layers = [estimate_layer(text, layer) for layer in ACTIVE_ROUTING_LAYERS]
    reserved_layers = [
        estimate_layer(text, layer)
        for layer in RESERVED_ROUTING_LAYERS
        if re.search(rf"(?m)^LAYER {re.escape(layer)}\s*$", text)
    ]
    report = {
        "schema": 1,
        "status": "engineering_estimate_not_foundry_qualified",
        "units": {
            "length": "um",
            "resistance": "ohm",
            "capacitance": "pF",
        },
        "source_basis": [
            {
                "path": "openIP62/IP62/Technology/doc/OS00_リファレンスマニュアル_rev1.1.pdf",
                "location": "pages 5 and 37-41",
                "fact": "The open manual lists parasitic extraction as unavailable and does not provide a metal RC/PEX deck.",
            },
            {
                "path": str(args.lef),
                "location": "M1/M2 and any declared reserved routing-layer statements",
                "fact": "The selected technology LEF supplies sheet resistance, area capacitance, edge capacitance, and nominal routing widths for its active and declared reserved routing layers.",
            },
        ],
        "method": {
            "resistance": "wire R = sheet_resistance * length / actual DEF route width; nominal per_um is the widthless-route fallback",
            "capacitance": "wire C = length * (area_capacitance * actual DEF route width + 2 * edge_capacitance); nominal per_um is the widthless-route fallback",
            "topology": "the extractor splits routed segments at endpoints, vias, and located DEF/LEF terminals and emits distributed RC edges",
            "vertical_overlap": "adjacent-metal overlap is modeled separately by the extractor from route bounding boxes",
            "sheet_resistance_relative_spread": SHEET_R_SPREAD,
            "capacitance_relative_spread": CAP_SPREAD,
            "spread_interpretation": "engineering sensitivity band, not a confidence interval",
        },
        "layers": layers,
        "reserved_layers": reserved_layers,
        "via": {
            "layer": "V1",
            "nominal_resistance_ohm": VIA_R_NOMINAL_OHM,
            "range_ohm": [VIA_R_LOW_OHM, VIA_R_HIGH_OHM],
            "basis": "No via resistance is published; nominal 1 ohm is an explicit local interconnect estimate for sensitivity analysis.",
        },
        "digital_flow_policy": {
            "routing_layers": list(ACTIVE_ROUTING_LAYERS),
            "reserved_routing_layers": list(RESERVED_ROUTING_LAYERS),
            "m3": "reserved_not_used_by_current_digital_router",
            "def_policy": "Reject routed DEF geometry on any layer outside routing_layers.",
            "timing_use": "Use nominal values for estimated RCX; evaluate the stated bands with sensitivity analysis.",
            "tapeout_status": "not signoff-qualified without foundry RC/PEX correlation.",
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for layer in layers:
        print(
            f"{layer['layer']}: R={layer['resistance_ohm_per_um']:.9f} ohm/um, "
            f"C={layer['capacitance_ff_per_um']:.6f} fF/um"
        )
    for layer in reserved_layers:
        print(
            f"{layer['layer']} (reserved): R={layer['resistance_ohm_per_um']:.9f} ohm/um, "
            f"C={layer['capacitance_ff_per_um']:.6f} fF/um"
        )
    print(f"V1: R={VIA_R_NOMINAL_OHM:.3f} ohm nominal [{VIA_R_LOW_OHM:.3f}, {VIA_R_HIGH_OHM:.3f}]")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
