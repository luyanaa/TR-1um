# TR-1um standard-cell timing comparison

## OpenSTA WNS period sweep

This comparison uses the regenerated seven-point Liberty characterization:

- Input transition grid: `0.5, 1, 2, 5, 10, 15, 20 ns`
- Output-load grid: `0.1, 0.5, 2.0 pF`
- Corner: `5.0 V`, `25 degC`

The post-layout netlist and distributed SPEF were held fixed for each design.
OpenSTA was run with the clock period `t` swept from `20` through `50 ns` in
`1 ns` steps. The existing input/output delays and `2 ns` clock uncertainty
were retained; only the `create_clock -period` value changed. Values below are
setup WNS from `worst_slack -max`, in ns.

| Design | WNS(20) | WNS(25) | WNS(30) | WNS(35) | WNS(40) | WNS(45) | WNS(50) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `tr1um_fifo4` | -15.549 | -10.549 | -5.549 | -0.549 | 4.451 | 9.451 | 14.451 |
| `tr1um_irqctrl` | -3.188 | 1.812 | 6.812 | 11.812 | 16.812 | 21.812 | 26.812 |
| `tr1um_spitx` | -13.631 | -8.631 | -3.631 | 1.369 | 6.369 | 11.369 | 16.369 |
| `tr1um_uarttx_big` | -19.495 | -14.495 | -9.495 | -4.495 | 0.505 | 5.505 | 10.505 |

The estimated `WNS = 0` period is linearly interpolated between the adjacent
1 ns samples that straddle zero:

| Design | Sign-change bracket | Estimated `WNS = 0` period (ns) |
|---|---|---:|
| `tr1um_fifo4` | `35 ns: -0.549` -> `36 ns: +0.451` | **35.549** |
| `tr1um_irqctrl` | `23 ns: -0.188` -> `24 ns: +0.812` | **23.188** |
| `tr1um_spitx` | `33 ns: -0.631` -> `34 ns: +0.369` | **33.631** |
| `tr1um_uarttx_big` | `39 ns: -0.495` -> `40 ns: +0.505` | **39.495** |

These are engineering comparison points from the current post-layout OpenSTA
views, not signoff maximum operating frequencies. They exclude additional
clock-model, variation, derating, and qualified-parasitic margins.
