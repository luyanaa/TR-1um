from __future__ import annotations

import json
import re
from pathlib import Path

import run_ohno_anchor_sweep as base

BASE_DECK = Path('/tmp/tr10-rcx/opamp/rcx/opamp.postlayout.renamed.sp')
OUTROOT = Path('/tmp/tr10-rcx/opamp/rcx_joint')
OUTROOT.mkdir(parents=True, exist_ok=True)
K_COUPLING = (0.8, 1.0, 1.2)
C_FIXTURE_PF = (50.0, 70.0, 100.0, 130.0, 150.0)
BIAS_UA = (11.50, 11.65, 11.80)
CASES = (
    ('vf_160k_1vpp', 'follower', 160e3, 0.5),
    ('vf_80k_2vpp', 'follower', 80e3, 1.0),
    ('vf_200k_1vpp', 'follower', 200e3, 0.5),
    ('vf_100k_2vpp', 'follower', 100e3, 1.0),
    ('inv_10k_2vpp', 'inverting', 10e3, 1.0),
)
NUMBER = r'([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)'
ORIGINAL_MAKE_DECK = base.make_deck


def scale_coupling_deck(target: Path, scale: float):
    lines = []
    for line in BASE_DECK.read_text().splitlines(keepends=True):
        if line.startswith('CPEX'):
            fields = line.split()
            is_ground_cap = len(fields) >= 4 and (fields[1] == 'P12' or fields[2] == 'P12')
            if len(fields) >= 4 and not is_ground_cap:
                match = re.search(rf'(\s){NUMBER}(pF\s*(?:\*.*)?\n?)$', line)
                if match:
                    value = float(match.group(2)) * scale
                    line = line[:match.start(2)] + f'{value:.12g}' + line[match.end(2):]
        lines.append(line)
    target.write_text(''.join(lines))


fixture_pf = 100.0

def make_joint_deck(path: Path, topology: str, bias: float, freq: float, amp: float, raw: Path):
    period, start, end = ORIGINAL_MAKE_DECK(path, topology, bias, freq, amp, raw)
    text = path.read_text()
    text = text.replace('CL OUT 0 100p', f'CL OUT 0 {fixture_pf:g}p')
    path.write_text(text)
    return period, start, end


base.make_deck = make_joint_deck
all_results = []
for k_c in K_COUPLING:
    variant = OUTROOT / f'k{k_c:g}'
    variant.mkdir(parents=True, exist_ok=True)
    deck = variant / 'opamp.postlayout.renamed.sp'
    scale_coupling_deck(deck, k_c)
    base.DECK = deck
    for fixture in C_FIXTURE_PF:
        fixture_pf = fixture
        base.C_FIXTURE = fixture * 1e-12
        for bias_ua in BIAS_UA:
            bias = bias_ua * 1e-6
            for case, topology, freq, amp in CASES:
                tag = f'k{k_c:g}_cf{fixture:g}_ib{bias_ua:g}_{case}'
                base.OUTDIR = variant / f'cf{fixture:g}_ib{bias_ua:g}'
                base.OUTDIR.mkdir(parents=True, exist_ok=True)
                result = base.run_one(tag, topology, bias, freq, amp)
                result.update({
                    'k_c_coupling': k_c,
                    'fixture_pF': fixture,
                    'bias_uA': bias_ua,
                })
                all_results.append(result)
                raw = base.OUTDIR / f'{tag}.raw'
                if raw.exists():
                    raw.unlink()

(OUTROOT / 'results.json').write_text(json.dumps(all_results, indent=2, sort_keys=True))
print(json.dumps({
    'result_count': len(all_results),
    'output': str(OUTROOT / 'results.json'),
    'k_c_coupling': K_COUPLING,
    'fixture_pF': C_FIXTURE_PF,
    'bias_uA': BIAS_UA,
}, sort_keys=True))
