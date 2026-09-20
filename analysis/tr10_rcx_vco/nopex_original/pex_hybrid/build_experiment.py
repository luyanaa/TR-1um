#!/usr/bin/env python3
"""Build a historical-model VCO deck with the checked-in distributed PEX network.

The device/capacitor deck comes from the original-model no-PEX reference. The
RPEX/CPEX subcircuit is copied from the repaired engineering post-layout deck.
Only CPEX values are scaled; RPEX values and intentional CLEG capacitors are
left unchanged. The default substrate connection is deliberately the emitted
`VSS` node; `--substrate-node P30` tests the physically expected VSS pin.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
POSTLAYOUT = HERE.parent.parent / "remediated" / "vco" / "vco.post.sp"
NOPEX = HERE.parent / "vco.nopex.sp"

_VALUE_RE = re.compile(r"^([-+0-9.eE]+)([a-zA-Z]+)$")


def _extract_postlayout_parts() -> tuple[str, list[str]]:
    lines = POSTLAYOUT.read_text().splitlines()
    xpex = next(line for line in lines if line.startswith("XPEX_TR1UM "))
    start = next(i for i, line in enumerate(lines) if line.startswith(".SUBCKT tr1um_parasitics "))
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == ".ENDS tr1um_parasitics")
    return xpex, lines[start : end + 1]


def _scaled_cpex(line: str, scale: float) -> str:
    if not line.startswith("CPEX"):
        return line
    fields = line.split()
    match = _VALUE_RE.match(fields[-1])
    if match is None:
        raise ValueError(f"cannot parse CPEX value: {line}")
    value, unit = match.groups()
    fields[-1] = f"{float(value) * scale:.12g}{unit}"
    return " ".join(fields)


def build_hybrid(scale: float, substrate_node: str) -> str:
    xpex, pex_lines = _extract_postlayout_parts()
    xpex_fields = xpex.split()
    xpex_fields[1] = substrate_node
    xpex = " ".join(xpex_fields)
    pex_lines = [_scaled_cpex(line, scale) for line in pex_lines]

    nopex = NOPEX.read_text()
    marker = ".ENDS VCO"
    if nopex.count(marker) != 1:
        raise ValueError("expected exactly one VCO subcircuit")
    vco = nopex.replace(marker, xpex + "\n" + marker, 1)
    return vco.rstrip() + "\n\n" + "\n".join(pex_lines) + "\n"


def write_experiment(scale: float, substrate_node: str, vctrl: float, stop: str, tag: str) -> Path:
    out_dir = HERE / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    deck = out_dir / "vco.nopex.pex.sp"
    deck.write_text(build_hybrid(scale, substrate_node))
    tb = out_dir / "run.sp"
    tb.write_text(
        "* Historical ISHI-KAI MOS/passive models plus distributed engineering PEX.\n"
        f".include \"../../models/mos.f8862f775cad.lib\"\n"
        f".include \"../../models/passive.f8862f775cad.lib\"\n"
        ".include \"vco.nopex.pex.sp\"\n\n"
        "VDD PWR 0 5\n"
        f"VCTRL CTRL 0 {vctrl:.12g}\n"
        "XU OUT PWR PWR 0 0 CTRL CTRL VCO\n\n"
        ".options reltol=2e-3 abstol=1e-12 vntol=1e-6 method=gear gmin=1e-10 rshunt=1e12 trtol=7 itl4=10000\n"
        ".save v(OUT) v(PWR) v(CTRL) v(P2) v(P3) v(P8)\n"
        f".tran 1n {stop} uic\n"
        ".meas tran T1 WHEN v(OUT)=2.5 RISE=8\n"
        ".meas tran T2 WHEN v(OUT)=2.5 RISE=9\n"
        ".meas tran PERIOD PARAM='T2-T1'\n"
        ".meas tran FREQ PARAM='1/PERIOD'\n"
        f".meas tran VOUT_MIN MIN v(OUT) FROM=20u TO={stop}\n"
        f".meas tran VOUT_MAX MAX v(OUT) FROM=20u TO={stop}\n"
        ".end\n"
    )
    return tb


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=float, required=True, help="CPEX scale; RPEX/CLEG remain unchanged")
    parser.add_argument("--substrate-node", default="VSS", choices=("VSS", "P30"))
    parser.add_argument("--vctrl", type=float, default=3.5)
    parser.add_argument("--stop", default="400u")
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    tb = write_experiment(args.scale, args.substrate_node, args.vctrl, args.stop, args.tag)
    print(tb)


if __name__ == "__main__":
    main()
