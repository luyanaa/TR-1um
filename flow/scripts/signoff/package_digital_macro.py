#!/usr/bin/env python3
"""Package a signed-off TR-1um digital core for hierarchical reuse."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from pathlib import Path


def strict_ports(text: str, top: str) -> list[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        words = line.split()
        if len(words) >= 2 and words[0].upper() == ".SUBCKT" and words[1] == top:
            ports = words[2:]
            for continuation in lines[index + 1 :]:
                continued_words = continuation.split()
                if not continued_words or continued_words[0] != "+":
                    break
                ports.extend(continued_words[1:])
            return ports
    raise SystemExit(f"strict contract has no .SUBCKT {top}")


def lef_pins(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for match in re.finditer(r"(?ms)^\s*PIN\s+(\S+)\s*$\s*(.*?)(?=^\s*END\s+\1\s*$)", text):
        direction = re.search(r"(?m)^\s*DIRECTION\s+(INPUT|OUTPUT|INOUT)\s*;", match.group(2))
        if direction:
            result[match.group(1)] = direction.group(1).lower()
    return result


def verilog_interface(text: str, top: str) -> tuple[str, set[str]]:
    module = re.search(
        rf"(?ms)^module\s+{re.escape(top)}\s*\((.*?)\);(.*?)^endmodule\s*$", text
    )
    if not module:
        raise SystemExit(f"powered netlist has no module {top}")
    header_ports = " ".join(module.group(1).split())
    header = f"module {top} ({header_ports});"
    declarations: list[str] = []
    names: set[str] = set()
    for declaration in re.finditer(
        r"(?m)^\s*(input|output|inout)\s+(?:wire\s+|reg\s+)?(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s+)?([^;]+);",
        module.group(2),
    ):
        declarations.append(declaration.group(0).strip())
        base_names = [name.strip() for name in declaration.group(4).split(",")]
        if declaration.group(2) is None:
            names.update(base_names)
        else:
            high, low = int(declaration.group(2)), int(declaration.group(3))
            for base in base_names:
                names.update(f"{base}[{bit}]" for bit in range(min(low, high), max(low, high) + 1))
    return "(* blackbox *)\n" + header + "\n " + "\n ".join(declarations) + "\nendmodule\n", names


def symbol(top: str, ports: list[str], directions: dict[str, str]) -> str:
    inputs = [p for p in ports if directions[p] == "input"]
    outputs = [p for p in ports if directions[p] == "output"]
    supplies = [p for p in ports if directions[p] == "inout"]
    height = max(80, 20 * max(len(inputs), len(outputs)) + 20)
    lines = [
        "v {xschem version=3.4.8RC file_version=1.2}",
        'K {type=subcircuit\nformat="@name @pinlist @symname"\ntemplate="name=x1"\n}',
        f"T {{@symname}} -45 {-height // 2 - 16} 0 0 0.3 0.3 {{}}",
        f"T {{@name}} 135 {-height // 2 - 12} 0 0 0.2 0.2 {{}}",
        f"P 4 5 130 {-height // 2} -130 {-height // 2} -130 {height // 2} 130 {height // 2} 130 {-height // 2} {{}}",
    ]
    for index, pin in enumerate(inputs):
        y = -height // 2 + 20 + index * 20
        lines += [f"B 5 -152.5 {y-2.5} -147.5 {y+2.5} {{name={pin} dir=in}}", f"L 4 -150 {y} -130 {y} {{}}", f"T {{{pin}}} -125 {y-4} 0 0 0.2 0.2 {{}}"]
    for index, pin in enumerate(outputs):
        y = -height // 2 + 20 + index * 20
        lines += [f"B 5 147.5 {y-2.5} 152.5 {y+2.5} {{name={pin} dir=out}}", f"L 4 130 {y} 150 {y} {{}}", f"T {{{pin}}} 125 {y-4} 0 1 0.2 0.2 {{}}"]
    for index, pin in enumerate(supplies):
        x = -20 + index * 40
        y = -height // 2 - 20 if pin.upper() in {"VDD", "VCC"} else height // 2 + 20
        edge = -height // 2 if y < 0 else height // 2
        lines += [f"B 5 {x-2.5} {y-2.5} {x+2.5} {y+2.5} {{name={pin} dir=inout}}", f"L 7 {x} {y} {x} {edge} {{}}", f"T {{{pin}}} {x+5} {edge-4} 0 0 0.2 0.2 {{}}"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--top", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    signed = args.run_dir / "connected_power"
    sources = {
        f"{args.top}.gds": signed / f"{args.top}.connected_power.gds",
        f"{args.top}.lef": signed / f"{args.top}.macro.lef",
        f"{args.top}.strict.cir": signed / f"{args.top}.strict.cir",
        f"{args.top}.pnl.v": args.run_dir / "final" / "pnl" / f"{args.top}.pnl.v",
    }
    for source in sources.values():
        if not source.is_file():
            raise SystemExit(f"missing signed-off macro input: {source}")
    args.output.mkdir(parents=True, exist_ok=True)
    for name, source in sources.items():
        shutil.copy2(source, args.output / name)

    contract = (args.output / f"{args.top}.strict.cir").read_text()
    ports = strict_ports(contract, args.top)
    lef_text = (args.output / f"{args.top}.lef").read_text()
    directions = lef_pins(lef_text)
    directions["VSS"] = directions.get("GND", "inout")
    directions["VDD"] = directions.get("VDD", "inout")
    missing_lef = [pin for pin in ports if pin not in directions]
    if missing_lef:
        raise SystemExit(f"contract ports absent from macro LEF: {missing_lef}")
    blackbox, verilog_ports = verilog_interface((args.output / f"{args.top}.pnl.v").read_text(), args.top)
    normalized_verilog = {"VSS" if name.upper() == "GND" else name for name in verilog_ports}
    if set(ports) != normalized_verilog:
        raise SystemExit(
            "hierarchical interface mismatch: strict contract and powered Verilog differ\n"
            f"contract-only={sorted(set(ports)-normalized_verilog)}\n"
            f"verilog-only={sorted(normalized_verilog-set(ports))}"
        )
    (args.output / f"{args.top}.blackbox.v").write_text(blackbox)
    (args.output / f"{args.top}.sym").write_text(symbol(args.top, ports, directions))
    (args.output / "README.md").write_text(
        f"# {args.top} hierarchical macro bundle\n\n"
        f"Use `{args.top}.gds` and `{args.top}.lef` as the physical macro views. "
        f"Use `{args.top}.blackbox.v` during parent synthesis. In xschem, place "
        f"`{args.top}.sym` and add `.include {args.top}.strict.cir` to the parent "
        "SPICE netlist. For a hardened digital parent, pass the strict contract "
        "as an additional final argument to `flow/run_core_lvs.sh`. Supply net "
        "GND is normalized to VSS in the SPICE/LVS view.\n"
    )
    manifest = []
    for path in sorted(args.output.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            manifest.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (args.output / "SHA256SUMS").write_text("\n".join(manifest) + "\n")
    print(f"packaged hierarchical macro {args.top}: {len(ports)} verified ports -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
