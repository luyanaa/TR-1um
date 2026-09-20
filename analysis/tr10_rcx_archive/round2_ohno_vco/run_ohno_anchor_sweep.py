from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

MODEL = Path('/Users/yanlu/Documents/TR-1um/libs.tech/spice/models/ip62_models_calibrated')
DECK = Path('/tmp/tr10-rcx/opamp/rcx/opamp.postlayout.renamed.sp')
OUTDIR = Path('/tmp/tr10-rcx/opamp/anchor')
OUTDIR.mkdir(parents=True, exist_ok=True)
C_C = 8.856e-12
C_FIXTURE = 100e-12
SR_SILICON_NOM = 0.5e6

VECTORS = [
    'time', 'v(sig)', 'v(inp)', 'v(inn)', 'v(out)', 'v(xu.p2)',
    '@m.xu.x_1.m1[id]', '@m.xu.x_34.m1[id]',
    '@m.xu.x_53.m1[id]', '@m.xu.x_77.m1[id]', '@c.xu.c_52[i]',
]


def make_deck(path: Path, topology: str, bias: float, freq: float, amp: float, raw: Path):
    period = 1.0 / freq
    step = period / 400.0
    stop = max(8.0 * period, 8e-3 if freq <= 1e3 else 8.0 * period)
    start = 2.0 * period
    end = 7.5 * period
    if topology == 'follower':
        stimulus = f'''VSIG SIG 0 SIN(2.5 {amp:.16g} {freq:.16g})
RSIG SIG INP 1
RFB OUT INN 1
'''
    elif topology == 'inverting':
        stimulus = f'''VREF INP 0 2.5
VSIG SIG 0 SIN(2.5 {amp:.16g} {freq:.16g})
RIN SIG INN 10k
RFB OUT INN 10k
'''
    else:
        raise ValueError(topology)
    path.write_text(f'''* Ohno quantitative anchor: {topology}, bias={bias:.16g}, f={freq:.16g}, amp={amp:.16g}
.include "{MODEL}"
.include "{DECK}"
VDD_SRC PWR_SRC 0 5
RVDD PWR_SRC PWR 1
IBIAS BIAS 0 {bias:.16g}
{stimulus}CL OUT 0 100p
XU OUT PWR 0 INP INN BIAS OPAMP_OHNO
.options reltol=5e-3 abstol=1e-12 vntol=1e-6 gmin=1e-12 method=gear
.tran {step:.16g} {stop:.16g}
.control
run
wrdata {raw} {' '.join(VECTORS)}
.endc
.end
''')
    return period, start, end


def read_wrdata(path: Path):
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append([float(value) for value in line.split()])
    if not rows:
        raise RuntimeError(f'{path}: no data')
    width = 2 * len(VECTORS)
    if any(len(row) != width for row in rows):
        raise RuntimeError(f'{path}: expected {width} columns')
    return [row[0] for row in rows], [[row[2 * i + 1] for row in rows] for i in range(len(VECTORS))]


def derivative(values, times):
    result = [0.0] * len(values)
    for i in range(len(values)):
        if i == 0:
            j = 1
        elif i == len(values) - 1:
            j = i - 1
        else:
            left = i - 1
            right = i + 1
            result[i] = (values[right] - values[left]) / (times[right] - times[left])
            continue
        result[i] = (values[i] - values[j]) / (times[i] - times[j])
    return result


def max_abs(values):
    return max((abs(value) for value in values), default=0.0)


def rms(values):
    return math.sqrt(sum(value * value for value in values) / len(values))


def metric(tag: str, topology: str, bias: float, freq: float, amp: float, start: float, end: float, t, vectors):
    names = {name: vectors[i] for i, name in enumerate(VECTORS)}
    indices = [i for i, value in enumerate(t) if start <= value <= end]
    if len(indices) < 20:
        raise RuntimeError(f'{tag}: too few steady-state samples')
    tm = [t[i] for i in indices]
    sig = [names['v(sig)'][i] for i in indices]
    inp = [names['v(inp)'][i] for i in indices]
    inn = [names['v(inn)'][i] for i in indices]
    out = [names['v(out)'][i] for i in indices]
    p2 = [names['v(xu.p2)'][i] for i in indices]
    i_n = [names['@m.xu.x_1.m1[id]'][i] for i in indices]
    i_p = [names['@m.xu.x_34.m1[id]'][i] for i in indices]
    i_cc = [names['@c.xu.c_52[i]'][i] for i in indices]
    slope = derivative(out, tm)
    slope_cc = derivative([out[i] - p2[i] for i in range(len(out))], tm)
    drive = [i_n[i] - i_p[i] for i in range(len(i_n))]
    idx = max(range(len(slope)), key=lambda i: abs(slope[i]))
    expected = sig if topology == 'follower' else [5.0 - value for value in sig]
    err = [out[i] - expected[i] for i in range(len(out))]
    drive_at_slew = abs(drive[idx])
    slope_at_max = abs(slope[idx])
    out_max = max(out)
    out_min = min(out)
    result = {
        'tag': tag,
        'topology': topology,
        'bias_A': bias,
        'frequency_Hz': freq,
        'input_amplitude_V': amp,
        'input_vpp_V': max(sig) - min(sig),
        'output_vpp_V': out_max - out_min,
        'output_max_V': out_max,
        'output_min_V': out_min,
        'output_headroom_hi_V': 5.0 - out_max,
        'output_headroom_lo_V': out_min,
        'max_abs_slew_V_per_us': max_abs(slope) / 1e6,
        'drive_current_at_max_slew_uA': drive_at_slew * 1e6,
        'drive_current_peak_uA': max_abs(drive) * 1e6,
        'comp_current_peak_uA': max_abs(i_cc) * 1e6,
        'comp_voltage_slew_V_per_us': max_abs(slope_cc) / 1e6,
        'tracking_rms_V': rms(err),
        'tracking_peak_V': max_abs(err),
        'inverting_input_error_peak_V': max_abs([value - 2.5 for value in inn]),
        'ceff_at_model_slew_pF': drive_at_slew / max(slope_at_max, 1e-30) * 1e12,
        'ceff_from_silicon_nominal_pF': drive_at_slew / SR_SILICON_NOM * 1e12,
        'cunexplained_vs_100pF_fixture_pF': drive_at_slew / SR_SILICON_NOM * 1e12 - C_C * 1e12 - C_FIXTURE * 1e12,
        'sample_count': len(indices),
    }
    return result


def run_one(tag, topology, bias, freq, amp):
    deck = OUTDIR / f'{tag}.sp'
    log = OUTDIR / f'{tag}.log'
    raw = OUTDIR / f'{tag}.raw'
    _, start, end = make_deck(deck, topology, bias, freq, amp, raw)
    subprocess.run(['ngspice', '-b', '-o', str(log), str(deck)], check=True)
    t, vectors = read_wrdata(raw)
    return metric(tag, topology, bias, freq, amp, start, end, t, vectors)


def main():
    jobs = []
    for freq, amp in [(1e3, 0.5), (160e3, 0.5), (200e3, 0.5), (80e3, 1.0), (100e3, 1.0)]:
        jobs.append((f'vf_b11p8_{int(freq)}_{int(2*amp)}vpp', 'follower', 11.8e-6, freq, amp))
    for bias_uA in (11.8, 15.0, 20.0, 30.0, 40.0):
        jobs.append((f'vf_bias{bias_uA:g}u_100k_2vpp', 'follower', bias_uA * 1e-6, 100e3, 1.0))
    for bias_uA in (11.8, 20.0, 30.0, 40.0):
        for amp, label in ((0.5, '1vpp'), (1.0, '2vpp')):
            jobs.append((f'inv_bias{bias_uA:g}u_10k_{label}', 'inverting', bias_uA * 1e-6, 10e3, amp))
    results = []
    for job in jobs:
        results.append(run_one(*job))
        print(json.dumps(results[-1], sort_keys=True))
    (OUTDIR / 'results.json').write_text(json.dumps(results, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
