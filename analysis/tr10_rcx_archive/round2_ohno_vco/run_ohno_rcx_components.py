from __future__ import annotations

import json
import re
from pathlib import Path

import run_ohno_anchor_sweep as base

BASE_DECK = Path('/tmp/tr10-rcx/opamp/rcx/opamp.postlayout.renamed.sp')
OUTROOT = Path('/tmp/tr10-rcx/opamp/rcx_components')
OUTROOT.mkdir(parents=True, exist_ok=True)
SCALES = (0.5, 1.0, 2.0)
CASES = (
    ('vf_160k_1vpp', 'follower', 160e3, 0.5),
    ('vf_80k_2vpp', 'follower', 80e3, 1.0),
    ('vf_200k_1vpp', 'follower', 200e3, 0.5),
    ('vf_100k_2vpp', 'follower', 100e3, 1.0),
    ('vf_1k_5vpp', 'follower', 1e3, 2.5),
)
NUMBER = r'([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)'


def belongs(group: str, node1: str, node2: str) -> bool:
    is_ground = node1 == 'P12' or node2 == 'P12'
    is_output = node1.startswith('P7:') or node2.startswith('P7:')
    if group == 'ground':
        return is_ground
    if group == 'coupling':
        return not is_ground
    if group == 'output':
        return is_output
    raise ValueError(group)


def scale_group(target: Path, group: str, scale: float):
    lines = []
    for line in BASE_DECK.read_text().splitlines(keepends=True):
        if line.startswith('CPEX'):
            fields = line.split()
            if len(fields) >= 4 and belongs(group, fields[1], fields[2]):
                match = re.search(rf'(\s){NUMBER}(pF\s*(?:\*.*)?\n?)$', line)
                if match:
                    value = float(match.group(2)) * scale
                    line = line[:match.start(2)] + f'{value:.12g}' + line[match.end(2):]
        lines.append(line)
    target.write_text(''.join(lines))


all_results = []
for group in ('ground', 'coupling', 'output'):
    for scale in SCALES:
        variant = OUTROOT / f'{group}_{scale:g}'
        variant.mkdir(parents=True, exist_ok=True)
        deck = variant / 'opamp.postlayout.renamed.sp'
        scale_group(deck, group, scale)
        base.DECK = deck
        base.OUTDIR = variant
        for case, topology, freq, amp in CASES:
            tag = f'{group}_{scale:g}_{case}'
            result = base.run_one(tag, topology, 11.8e-6, freq, amp)
            result['component_group'] = group
            result['component_scale'] = scale
            all_results.append(result)
            raw = variant / f'{tag}.raw'
            if raw.exists():
                raw.unlink()

(OUTROOT / 'results.json').write_text(json.dumps(all_results, indent=2, sort_keys=True))
print(json.dumps({'result_count': len(all_results), 'output': str(OUTROOT / 'results.json')}, sort_keys=True))
