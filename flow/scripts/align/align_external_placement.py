#!/usr/bin/env python3
"""Deterministic external-placement adapter for the installed ALIGN API."""
from __future__ import annotations

import json
import pathlib
import re
from collections import defaultdict


def _primitive_data(input_dir: pathlib.Path):
    primitive_dir = input_dir.parent.parent / "2_primitives"
    manifest = json.loads((primitive_dir / "__primitives__.json").read_text())
    by_abstract = defaultdict(list)
    dimensions = {}
    for concrete_name, record in manifest.items():
        by_abstract[record["abstract_template_name"]].append(concrete_name)
        bbox = json.loads((primitive_dir / f"{concrete_name}.json").read_text())["bbox"]
        dimensions[concrete_name] = (bbox[2] - bbox[0], bbox[3] - bbox[1])
    return by_abstract, dimensions


def build_scaled_placement(input_dir: pathlib.Path, placement_file: pathlib.Path, top_name: str) -> dict:
    generated = json.loads((input_dir / f"{top_name.upper()}.verilog.json").read_text())
    module = generated["modules"][0]
    source = json.loads(placement_file.read_text())["modules"][0]
    source_instances = {x["instance_name"]: x for x in source["instances"]}
    by_abstract, dimensions = _primitive_data(input_dir)

    mapped = []
    for instance in module["instances"]:
        source_instance = source_instances.get(instance["instance_name"])
        if source_instance is None:
            raise ValueError(f"external placement lacks {instance['instance_name']}")
        abstract = instance["abstract_template_name"]
        candidates = by_abstract.get(abstract, [])
        if len(candidates) != 1:
            raise ValueError(f"expected one primitive for {abstract}, found {candidates}")
        concrete = candidates[0]
        width, height = dimensions[concrete]
        tr = source_instance["transformation"]
        mapped.append({
            "instance": instance,
            "concrete": concrete,
            "width": width,
            "height": height,
            "source_y": tr["oY"],
            "source_x": tr["oX"],
            "sX": tr["sX"],
            "sY": tr["sY"],
        })

    mapped.sort(key=lambda x: (x["source_y"], x["source_x"], x["instance"]["instance_name"]))
    total_height = sum(x["height"] for x in mapped)
    total_width = max(x["width"] for x in mapped)
    instances = []
    y = 0
    for item in mapped:
        left = (total_width - item["width"]) // 2
        bottom = y
        y += item["height"]
        sx, sy = item["sX"], item["sY"]
        instances.append({
            "instance_name": item["instance"]["instance_name"],
            "fa_map": item["instance"]["fa_map"],
            "abstract_template_name": item["instance"]["abstract_template_name"],
            "concrete_template_name": item["concrete"],
            "transformation": {
                "oX": left + (item["width"] if sx == -1 else 0),
                "oY": bottom + (item["height"] if sy == -1 else 0),
                "sX": sx,
                "sY": sy,
            },
        })

    return {
        "modules": [{
            "parameters": module.get("parameters", []),
            "constraints": module.get("constraints", []),
            "instances": instances,
            "abstract_name": module["name"],
            "concrete_name": module["name"] + "_0",
            "bbox": [0, 0, total_width, total_height],
        }],
        "leaves": [],
        "global_signals": generated.get("global_signals", []),
    }


def make_placer_driver(placement_file: pathlib.Path, top_name: str):
    from align.pnr import placer as placer_module

    def external_placer_driver(*, cap_map, cap_lef_s, lambda_coeff, scale_factor,
                                select_in_ILP, place_using_ILP, seed,
                                use_analytical_placer, ilp_solver, primitives,
                                toplevel_args_d, results_dir,
                                placer_sa_iterations, placer_ilp_runtime,
                                black_box_flow):
        fpath = toplevel_args_d["input_dir"]
        idir = pathlib.Path(fpath)
        pairs = []
        pattern = re.compile(r"^(\S+)\s+(\S+)\s*$")
        for line in (idir / toplevel_args_d["map_file"]).read_text().splitlines():
            match = pattern.match(line)
            if not match:
                raise ValueError(f"invalid map entry: {line!r}")
            pairs.append(match.groups())
        lef_s_in = None
        if cap_map:
            pairs.extend(cap_map)
            lef_s_in = (idir / toplevel_args_d["lef_file"]).read_text() + cap_lef_s
        DB, verilog_d, new_fpath, opath, num_layout, effort = placer_module.gen_DB_verilog_d(
            toplevel_args_d=toplevel_args_d, results_dir=results_dir,
            map_d_in=pairs, lef_s_in=lef_s_in)
        if new_fpath != fpath:
            raise ValueError(f"ALIGN changed placement input path: {new_fpath} != {fpath}")
        placement = build_scaled_placement(idir, placement_file, top_name)
        return placer_module.hierarchical_place(
            DB=DB, opath=opath, fpath=fpath, numLayout=num_layout,
            effort=effort, verilog_d=verilog_d, lambda_coeff=lambda_coeff,
            scale_factor=scale_factor, placement_verilog_d=placement,
            select_in_ILP=False, place_using_ILP=False, seed=seed,
            use_analytical_placer=False, ilp_solver=ilp_solver,
            primitives=primitives, placer_sa_iterations=placer_sa_iterations,
            placer_ilp_runtime=placer_ilp_runtime,
            black_box_flow=black_box_flow)

    return external_placer_driver
