from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

POST_TB = Path('/tmp/tr10-rcx/converted/rcx/reduced/vco.post.tb.sp')
POST_SP = Path('/tmp/tr10-rcx/converted/rcx/reduced/vco.post.sp')
PRE_TB = Path('/tmp/tr10-rcx/converted/rcx/vco.control.pre.tb.sp')
PRE_LOG = Path('/tmp/tr10-rcx/converted/rcx/vco.control.pre.log')
OUTROOT = Path('/tmp/tr10-rcx/converted/rcx/reduced/vco_crosscheck')
FACTORS = (0.8, 1.0, 1.2)
NUMBER = r'([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)'


def scale_coupling(post_text: str, factor: float):
    out = []
    total = ground = coupling = 0
    for line in post_text.splitlines(keepends=True):
        fields = line.split()
        if fields and fields[0].startswith('CPEX') and len(fields) >= 4:
            total += 1
            is_ground = fields[1] == 'P1' or fields[2] == 'P1'
            if is_ground:
                ground += 1
            else:
                coupling += 1
                match = re.search(rf'(\s){NUMBER}(pF\s*(?:\*.*)?\n?)$', line)
                if not match:
                    raise RuntimeError(f'cannot parse CPEX value: {line.rstrip()}')
                value = float(match.group(2)) * factor
                line = line[:match.start(2)] + f'{value:.12g}' + line[match.end(2):]
        out.append(line)
    return ''.join(out), {'cpex_total': total, 'ground_entries': ground, 'coupling_entries': coupling}


def make_tb(path: Path, post_path: Path):
    text = POST_TB.read_text()
    text = text.replace(str(POST_SP), str(post_path))
    path.write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='store_true', help='run each prepared 100 us candidate')
    args = parser.parse_args()
    OUTROOT.mkdir(parents=True, exist_ok=True)
    post_text = POST_SP.read_text()
    variants = []
    counts = None
    for factor in FACTORS:
        d = OUTROOT / f'k{factor:g}'
        d.mkdir(parents=True, exist_ok=True)
        post_path = d / 'vco.post.sp'
        scaled, current_counts = scale_coupling(post_text, factor)
        counts = current_counts if counts is None else counts
        if current_counts != counts:
            raise RuntimeError(f'CPEX count changed for factor {factor}: {current_counts} != {counts}')
        post_path.write_text(scaled)
        tb_path = d / 'vco.post.tb.sp'
        make_tb(tb_path, post_path)
        row = {
            'k_c_coupling': factor,
            'postlayout_spice': str(post_path),
            'testbench': str(tb_path),
            'status': 'prepared',
        }
        if args.run:
            import subprocess
            log_path = d / 'vco.post.log'
            subprocess.run(['ngspice', '-b', '-o', str(log_path), str(tb_path)], check=True)
            row['log'] = str(log_path)
            row['status'] = 'ran'
        variants.append(row)
    reference = {
        'frequency_Hz': 7.45178e5,
        'period_s': 1.34196e-6,
        'source_testbench': str(PRE_TB),
        'source_log': str(PRE_LOG),
        'interpretation': 'pre-layout controlled simulation reference, not a silicon measurement',
    }
    manifest = {
        'design': 'TR10-1 VCO',
        'base_postlayout_spice': str(POST_SP),
        'base_testbench': str(POST_TB),
        'supply_V': 5.0,
        'control_V': 2.5,
        'transient': '10n 100u uic',
        'fixture_capacitance': 'none added; use VCO testbench as-is',
        'bias_nuisance': 'not applicable; VCO has no Ohno IB source',
        'factor_definition': 'scale only non-P1 CPEX coupling entries; preserve P1 ground entries, device model, and RPEX',
        'cpex_counts': counts,
        'reference': reference,
        'variants': variants,
        'limitations': [
            'engineering-estimate PEX, not foundry-qualified RCX',
            'reduced ledger uses tr1um_parasitic_model_no_lateral.json',
            'lateral-coupling sensitivity is not represented by this factor sweep',
        ],
    }
    out = OUTROOT / 'manifest.json'
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps({'manifest': str(out), 'cpex_counts': counts, 'variants': len(variants), 'ran': args.run}, sort_keys=True))


if __name__ == '__main__':
    main()
