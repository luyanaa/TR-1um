#!/usr/bin/env python3
"""Build a non-circular transistor-level LVS contract for a digital core.

Connectivity comes from the routed powered Verilog netlist.  Transistor
topology comes from the checked-in standard-cell CDL.  The layout extraction
is used only for hierarchy/pin order, including ports purged as unused.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path


def liberty_blocks(text: str, keyword: str) -> dict[str, str]:
    """Return balanced ``keyword (name) { ... }`` blocks from Liberty text."""
    result: dict[str, str] = {}
    pattern = re.compile(rf"(?i)\b{re.escape(keyword)}\s*\(\s*([^()]+?)\s*\)\s*\{{")
    for match in pattern.finditer(text):
        depth = 1
        index = match.end()
        quoted = False
        escaped = False
        while index < len(text) and depth:
            char = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            index += 1
        if depth:
            raise ValueError(f"unterminated Liberty {keyword} block {match.group(1)}")
        result[match.group(1).strip().upper()] = text[match.start():index]
    return result


def liberty_pin_directions(text: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for cell, block in liberty_blocks(text, "cell").items():
        directions: dict[str, str] = {}
        for pin, pin_block in liberty_blocks(block, "pin").items():
            match = re.search(r"(?i)\bdirection\s*:\s*([A-Za-z_]+)\s*;", pin_block)
            if match:
                directions[pin] = match.group(1).lower()
        result[cell] = directions
    return result


def circuits(text: str) -> dict[str, str]:
    return {
        match.group(1).upper(): match.group(0).strip()
        for match in re.finditer(
            r"(?ims)^\.subckt\s+(\S+).*?^\.ends(?:\s+\S+)?\s*$", text
        )
    }


def port_order(circuit: str) -> list[str]:
    # SPICE continues long .SUBCKT headers on any number of lines beginning
    # with '+'.  Collect them explicitly; treating only the first physical
    # line silently drops top-level bus and supply ports in larger macros.
    lines = circuit.splitlines()
    for index, line in enumerate(lines):
        words = line.split()
        if words and words[0].upper() == ".SUBCKT":
            ports = words[2:]
            for continuation in lines[index + 1 :]:
                continued_words = continuation.split()
                if not continued_words or continued_words[0] != "+":
                    break
                ports.extend(continued_words[1:])
            return ports
    raise ValueError("missing .SUBCKT header")


def verilog_instances(text: str, cells: set[str]) -> list[tuple[str, str, dict[str, str]]]:
    result: list[tuple[str, str, dict[str, str]]] = []
    for cell, instance, arguments in re.findall(
        r"(?ms)^\s*([A-Za-z_][A-Za-z0-9_$]*)\s+(\S+)\s*\((.*?)\);", text
    ):
        if cell.upper() not in cells:
            continue
        named = {
            pin.upper(): net
            for pin, net in re.findall(
                r"\.([A-Za-z0-9_]+)\s*\(\s*([^()\s]+)\s*\)", arguments
            )
        }
        if not named:
            raise ValueError(f"instance {instance} of {cell} has no named connections")
        result.append((cell.upper(), instance, named))
    return result


def translate_net(net: str, aliases: dict[str, str] | None = None) -> str:
    if aliases is not None and net in aliases:
        return aliases[net]
    if net.upper() in {"GND", "VSS"}:
        return "VSS"
    if net.upper() in {"VDD", "VCC"}:
        return "VDD"
    return net


def physical_top_instances(circuit: str) -> Counter[str]:
    return Counter(
        line.split()[-1].upper()
        for line in circuit.splitlines()
        if line.lstrip()[:1].upper() == "X"
    )


def normalized_cdl(source: str, name: str, pins: list[str]) -> str:
    lines = source.splitlines()
    if len(lines) < 3:
        raise ValueError(f"malformed CDL circuit {name}")
    body = "\n".join(lines[1:-1])
    source_pins = {pin.upper() for pin in port_order(source)}
    mos_bulk: dict[str, set[str]] = {"PMOS": set(), "NMOS": set()}
    for line in body.splitlines():
        words = line.split()
        if len(words) >= 6 and words[0][:1].upper() == "M":
            model = words[5].upper()
            if model in mos_bulk:
                mos_bulk[model].add(words[4])
    for aliases, model, replacement in (
        ({"VDD", "VCC"}, "PMOS", "VDD"),
        ({"GND", "VSS"}, "NMOS", "VSS"),
    ):
        if source_pins & aliases:
            continue
        candidates = mos_bulk[model]
        if len(candidates) != 1:
            raise ValueError(
                f"{name} lacks a {replacement} port and has non-unique {model} "
                f"bulk nodes: {sorted(candidates)}"
            )
        old = next(iter(candidates))
        body = re.sub(rf"(?<!\S){re.escape(old)}(?!\S)", replacement, body)
    source_pins = {pin.upper() for pin in port_order(source)}

    # Some legacy access-cell CDL blocks lost a supply label during their
    # original extraction (OR3 calls its common PMOS bulk net "$9", for
    # example). Recover only an absent supply from the unique MOS bulk node;
    # this uses the checked-in transistor contract, not the routed core.
    for aliases, model, replacement in (
        ({"VDD", "VCC"}, "PMOS", "VDD"),
        ({"GND", "VSS"}, "NMOS", "VSS"),
    ):
        if source_pins & aliases:
            continue
        bulk_nodes = {
            words[4]
            for line in body.splitlines()
            if len((words := line.split())) >= 6 and words[0].upper().startswith("M")
            and words[5].upper() == model
        }
        if len(bulk_nodes) != 1:
            raise ValueError(
                f"{name} lacks {replacement} port and has ambiguous {model} bulk nodes: "
                f"{sorted(bulk_nodes)}"
            )
        old = next(iter(bulk_nodes))
        body = re.sub(rf"(?<!\S){re.escape(old)}(?!\S)", replacement, body)
    body = re.sub(r"(?i)(?<![A-Za-z0-9_$])(?:gnd|vss)(?![A-Za-z0-9_$])", "VSS", body)
    body = re.sub(r"(?i)(?<![A-Za-z0-9_$])(?:vdd|vcc)(?![A-Za-z0-9_$])", "VDD", body)
    normalized_pins = [translate_net(pin) for pin in pins]
    return f".SUBCKT {name} {' '.join(normalized_pins)}\n{body}\n.ENDS {name}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--physical-extracted", required=True, type=Path)
    parser.add_argument("--powered-netlist", required=True, type=Path)
    parser.add_argument("--cell-cdl", required=True, type=Path)
    parser.add_argument("--cell-liberty", required=True, type=Path)
    parser.add_argument("--macro-contract", action="append", default=[], type=Path)
    parser.add_argument("--top", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    physical = circuits(args.physical_extracted.read_text())
    source_cdl = circuits(args.cell_cdl.read_text())
    pin_directions = liberty_pin_directions(args.cell_liberty.read_text())
    for contract in args.macro_contract:
        source_cdl.update(circuits(contract.read_text()))
    top_key = args.top.upper()
    if top_key not in physical:
        raise SystemExit(f"ERROR: physical extraction has no top {args.top}")

    powered_text = args.powered_netlist.read_text()
    constant_aliases: dict[str, str] = {}
    for cell, _, named in verilog_instances(powered_text, {"TIEHI", "TIELO"}):
        pin = "HI" if cell == "TIEHI" else "LO"
        if pin in named:
            constant_aliases[named[pin]] = "VDD" if cell == "TIEHI" else "VSS"

    common_cells = set(physical) & set(source_cdl)
    instances = verilog_instances(powered_text, common_cells)
    if not instances:
        raise SystemExit("ERROR: no standard-cell instances found in powered Verilog")

    intended_population = Counter(cell for cell, _, _ in instances)
    extracted_population = physical_top_instances(physical[top_key])
    if intended_population != extracted_population:
        print(f"Verilog population:  {dict(sorted(intended_population.items()))}")
        print(f"physical population: {dict(sorted(extracted_population.items()))}")
        raise SystemExit("ERROR: Verilog and physical instance populations differ")

    # Never let extraction silently discard a required leaf-cell input.  In
    # particular, a physically floating DFFR RST terminal disappears from the
    # extracted .SUBCKT header.  Unused output pins (for example DFFR.QB) may
    # legitimately disappear, so use Liberty directions rather than assuming
    # that every declared signal pin must remain in the extracted interface.
    supply_pins = {"VDD", "VCC", "GND", "VSS"}
    for cell in sorted(intended_population):
        if cell not in pin_directions:
            raise SystemExit(f"ERROR: Liberty has no cell {cell} for input-pin validation")
        intended_signals = {
            pin.upper()
            for pin, direction in pin_directions[cell].items()
            if direction in {"input", "inout"} and pin.upper() not in supply_pins
        }
        physical_signals = {
            pin.upper() for pin in port_order(physical[cell])
        } - supply_pins
        missing = intended_signals - physical_signals
        if missing:
            raise SystemExit(
                f"ERROR: physical {cell} lost intended signal pin(s) "
                f"{', '.join(sorted(missing))}; likely floating or unlabelled layout geometry"
            )

    top_pins = [translate_net(pin) for pin in port_order(physical[top_key])]
    if len(top_pins) != len(set(pin.upper() for pin in top_pins)):
        raise SystemExit(f"ERROR: aliased/duplicate physical top pins: {top_pins}")

    top_lines = [f".SUBCKT {args.top} {' '.join(top_pins)}"]
    for cell, instance, named in instances:
        nets: list[str] = []
        for physical_pin in port_order(physical[cell]):
            pin = physical_pin.upper()
            if pin in {"GND", "VSS"}:
                nets.append("VSS")
            elif pin in {"VDD", "VCC"}:
                nets.append("VDD")
            elif pin in named:
                nets.append(translate_net(named[pin], constant_aliases))
            else:
                raise SystemExit(
                    f"ERROR: Verilog instance {instance} ({cell}) has no {physical_pin} connection"
                )
        top_lines.append(f"X{instance} {' '.join(nets)} {cell}")
    top_lines.append(f".ENDS {args.top}")

    body = [
        "* Generated strict digital-core LVS contract; do not hand-edit.",
        "* Connectivity: powered routed Verilog. Leaf devices: checked-in cell CDL.",
        "\n".join(top_lines),
    ]
    needed = set(intended_population)
    pending = list(needed)
    while pending:
        cell = pending.pop()
        for line in source_cdl[cell].splitlines():
            if line.lstrip()[:1].upper() != "X":
                continue
            child = line.split()[-1].upper()
            if child not in needed:
                if child not in source_cdl or child not in physical:
                    raise SystemExit(
                        f"ERROR: {cell} depends on unavailable physical/contract cell {child}"
                    )
                needed.add(child)
                pending.append(child)
    for cell in sorted(needed):
        body.append(normalized_cdl(source_cdl[cell], cell, port_order(physical[cell])))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(body) + "\n")
    print(
        f"wrote {args.output}: {sum(intended_population.values())} instances, "
        f"{len(intended_population)} cell types, top pins {' '.join(top_pins)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
