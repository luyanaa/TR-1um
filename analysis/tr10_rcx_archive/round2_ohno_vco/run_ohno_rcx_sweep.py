from __future__ import annotations

import json
import re
from pathlib import Path

import run_ohno_anchor_sweep as base

BASE_DECK = Path('/tmp/tr10-rcx/opamp/rcx/opamp.postlayout.renamed.sp')
OUTROOT = Path('/tmp/tr10-rcx/opamp/rcx_sweep')
OUTROOT.mkdir(parents=True, exist_ok=True)
SCALES = (0.25, 0.5, 1.0, 2.0, 4.0)
CASES = (
    ('vf_160k_1vpp', 'follower', 160e3, 0.5),
    ('vf_80k_2vpp', 'follower', 80e3, 1.0),
    ('vf_200k_1vpp', 'follower', 200e3, 0.5),
    ('vf_100k_2vpp', 'follower', 100e3, 1.0),
    ('inv_10k_2vpp', 'inverting', 10e3, 1.0),
    ('vf_1k_5vpp', 'follower', 1e3, 2.5),
)


def scale_deck(r_scale: float, c_scale: float, target: Path):
    out = []
    number = r'([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)'
    for line in BASE_DECK.read_text().splitlines(keepends=True):
        if line.startswith('RPEX'):
            match = re.search(rf'(\s){number}(\s*(?:\*.*)?\n?)$', line)
            if match:
                value = float(match.group(2)) * r_scale
                line = line[:match.start(2)] + f'{value:.12g}' + line[match.end(2):]
        elif line.startswith('CPEX'):
            match = re.search(rf'(\s){number}(pF\s*(?:\*.*)?\n?)$', line)
            if match:
                value = float(match.group(2)) * c_scale
                line = line[:match.start(2)] + f'{value:.12g}' + line[match.end(2):]
        out.append(line)
    target.write_text(''.join(out))


def run_variant(r_scale: float, c_scale: float):
    variant = OUTROOT / f'r{r_scale:g}_c{c_scale:g}'
    variant.mkdir(parents=True, exist_ok=True)
    deck = variant / 'opamp.postlayout.renamed.sp'
    scale_deck(r_scale, c_scale, deck)
    base.DECK = deck
    base.OUTDIR = variant
    results = []
    for case, topology, freq, amp in CASES:
        tag = f'r{r_scale:g}_c{c_scale:g}_{case}'
        result = base.run_one(tag, topology, 11.8e-6, freq, amp)
        result['r_scale'] = r_scale
        result['c_scale'] = c_scale
        results.append(result)
        raw = variant / f'{tag}.raw'
        if raw.exists():
            raw.unlink()
    return results


all_results = []
for r_scale in SCALES:
    for c_scale in ((1.0,) if r_scale != 1.0 else SCALES):
        all_results.extend(run_variant(r_scale, c_scale))

(OUTROOT / 'results.json').write_text(json.dumps(all_results, indent=2, sort_keys=True))
print(json.dumps({'result_count': len(all_results), 'output': str(OUTROOT / 'results.json')}, sort_keys=True))
