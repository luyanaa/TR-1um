from __future__ import annotations

import json
import re
from pathlib import Path

import run_ohno_anchor_sweep as base

BASE_DECK = Path('/tmp/tr10-rcx/opamp/rcx/opamp.postlayout.renamed.sp')
OUTROOT = Path('/tmp/tr10-rcx/opamp/rcx_cfine')
OUTROOT.mkdir(parents=True, exist_ok=True)
C_SCALES = (0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0)
CASES = (
    ('vf_160k_1vpp', 'follower', 160e3, 0.5),
    ('vf_80k_2vpp', 'follower', 80e3, 1.0),
    ('vf_200k_1vpp', 'follower', 200e3, 0.5),
    ('vf_100k_2vpp', 'follower', 100e3, 1.0),
    ('vf_1k_5vpp', 'follower', 1e3, 2.5),
)


def scale_capacitances(target: Path, scale: float):
    number = r'([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)'
    lines = []
    for line in BASE_DECK.read_text().splitlines(keepends=True):
        if line.startswith('CPEX'):
            match = re.search(rf'(\s){number}(pF\s*(?:\*.*)?\n?)$', line)
            if match:
                value = float(match.group(2)) * scale
                line = line[:match.start(2)] + f'{value:.12g}' + line[match.end(2):]
        lines.append(line)
    target.write_text(''.join(lines))


all_results = []
for c_scale in C_SCALES:
    variant = OUTROOT / f'c{c_scale:g}'
    variant.mkdir(parents=True, exist_ok=True)
    deck = variant / 'opamp.postlayout.renamed.sp'
    scale_capacitances(deck, c_scale)
    base.DECK = deck
    base.OUTDIR = variant
    for case, topology, freq, amp in CASES:
        tag = f'c{c_scale:g}_{case}'
        result = base.run_one(tag, topology, 11.8e-6, freq, amp)
        result['c_scale'] = c_scale
        all_results.append(result)
        raw = variant / f'{tag}.raw'
        if raw.exists():
            raw.unlink()

(OUTROOT / 'results.json').write_text(json.dumps(all_results, indent=2, sort_keys=True))
print(json.dumps({'result_count': len(all_results), 'output': str(OUTROOT / 'results.json')}, sort_keys=True))
