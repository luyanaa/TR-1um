# TR-1um Open Source PDK project (NDA-free 1um CMOS PDK)

The TR-1um Open Source PDK project, a new NDA-Free PDK ecosystem in Japan, is supported by the non-profit OpenSUSI (Open Source Utilized Silicon Initiatives). [**Tokai Rika**](https://tr-semicon.tokai-rika.co.jp/foundry-service) approved to open their PDK and manufacture the data, which is designed by the Open Source EDA tool at Tokai Rika's facility.

The original document and the DRC/LVS runsets are deliverable as-is by Tokai Rika. Yet, the OpenSUSI proposes new PDK package development based on the Drawing layer + MDP (Mask Development Preparation) procedure. Please see [Manifest](Document/Manifesto.md).

**We welcome your feedback and advice.** We are also planning the Shuttle service once any budgets are in place.

# TR-1um Directory Structure 
```
TR-1um -- openIP62 -- AnagixLoader
       |           +- IP62
       +- STDLIB ----- extracted
       |
       +- libs.tech -- klayout
       |            +- spice
       |            +- xschem
       +- Tools
       +- Document
       +- flow ----- LibreLane/ALIGN integration (see flow/README.md)
```

Since the original DRC cannot check a full-custom layout, such as Standard Cell development, except for PCEL use, new DRC runset development is ongoing under the tech/drc directory. Additionally, the [Tutorial: How to make DRC runset for KLayout](Document/Tutorials/Tutorial_DRC.md) and the [Tutorial: How to make LVS runset for KLayout](Document/Tutorials/Tutorial_LVS.md) project are also ongoing; feel free to join as always. We welcome your feedback on the DRC result and bug report as well.

## openIP62 (AS-IS)
The directory contains the original PDKs provided by [**Tokai Rika**](https://tr-semicon.tokai-rika.co.jp/foundry-service). It includes two main subdirectories: **AnagixLoader** and **IP62**. Detailed documentation and installation manuals (in Japanese) can be found in: **openIP62/IP62/Technology/doc**

## STDLIB
Extracted spice files from **openIP62/IP62/Basic/libraries/xxx.gds** by LVS operation which are including AD/AS/PD/PS information.

## libs.tech
The active technology collateral is under `libs.tech/klayout/tech`; the
repository also contains the `spice` and `xschem` libraries.

### Contents
| Directory | Description |
| --- | --- |
| `klayout/tech` | KLayout DRC/LVS/PCells, layer files, and technology collateral. |
| `spice` | SPICE-related library collateral. |
| `xschem` | Xschem symbol library under development. |

## Acknowledgements

This flow incorporates part of the optional auxiliary standard-cell collateral
from [KoheiUchi/TR_1um_sc](https://github.com/KoheiUchi/TR_1um_sc), including
`DFFQU1`, `FA1D1`, and `HA1S`, which are layout-compatible with the TR-1um
standard-cell library. Source-derived views are staged under
`flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell/aux`, with the opt-in LibreLane
integration in `flow/pdk_root/TR-1um/libs.tech/librelane/aux_stdcell.tcl`.
These cells remain outside the default cell contract pending timing
characterization and independent qualification.

## Tools

- Tools/IP62_to_TR-1um.py  INPUT_TR62.gds OUTPUT_TR-1um.gds

       IP62(MASK Layers) to TR-1um(Drawing Layers) conversion Python script, which is hierachically execute it bottom to top.

- Tools/DR_csv2py.py rules_def.py

       TR-1um_DR(Design Rule Table) to Python Class file script.

- Tools/DR_csv2drc.py run.drc

       TR-1um_DR(Design Rule Table) to KLayout DRC runset file script.

## Document

[Manifesto: PDK renewal for TR-1um technology](Document/Manifesto.md)

[New Desgin Rule Summary Manual](Document/TR-1um_DRC_summary.pdf) (PDF)

[Design Rule Table for Drawing Layers](Document/TR-1um_Drawing_Layer_DR_Table.xlsx) (XLS)

[Drawing Layer vs Mask Layer Table](Document/TR-1um_GDSII_Table.xlsx) (XLS)

[Tutorial: How to make DRC runset for KLayout](Document/Tutorials/Tutorial_DRC.md)

[Tutorial: How to make LVS runset for KLayout](Document/Tutorials/Tutorial_LVS.md) 

[Tutorial: How to make PCell python script for KLayout](Document/Tutorials/Tutorial_PCell.md) 

[Layers and Design steps: Layers reenewal for TR-1um technology](Document/Drawing_vs_Mask.md)

## Roadmap and status

### Completed

- Drawing-layer DRC/LVS/MDP runsets (KLayout) replacing the mask-layer plus
  recognition-layer (DLXXX) design flow; recognition layers are no longer
  required for device extraction.
- MASK → Drawing and Drawing → MASK conversion tools under `Tools/`.
- PCell sets for drawing-layer layout; DRC runset auto-generated from the
  design-rule table (`Tools/DR_csv2py.py` → `libs.tech/klayout/tech/python/cells/rules_def.py`,
  `Tools/DR_csv2drc.py` → `libs.tech/klayout/tech/drc/run.drc`).
- NF/PF-to-PSUB matching check; full-custom support for MP/MN/MPE/MNE/RR/RS/CSIO;
  surrounding-SG tie-down check for RR; off-grid/not-diagonal checks; fat-M2 rule
  defined as same as M1.
- Initial LVS runset (MOS/DIODE/CAP/RR/RS) including RR/RS L/W comparison;
  DRC and LVS tutorials.
- Two-metal multi-transistor ALIGN primitive generator (M1 net trunks + V1
  crossings replacing ALIGN's M3 bridge); DCL/SCM/CMC now generate valid ALIGN
  collateral with no new DRC categories.
- The `TR-1um_MPW_template` submission contract is pinned as a git submodule
  and integrated into the local pre-check/signoff gate.
- Engineering-only DEF/GDS/device-aware RCX is available under `flow/`.
  It emits a distributed RC/SPICE network, SPEF, and a provenance ledger, but
  it is not foundry-qualified.

### Planned

- Add ESD device checks to DRC/LVS.
- Use `TR-1um_DRC_Regression_TEST` (Cat-1 through Cat-9) as the DRC
  qualification gate before release.
- Obtain a reviewed foundry- or silicon-correlated RC/PEX deck to replace the
  current engineering estimate; validate layer RC, via RC, coupling, and
  device-capacitance ownership before calling extraction qualified.
- Qualify LibreLane PDN/routing/signoff against the MPW template and the
  TR-1um DRC/LVS/MDP regression before tapeout use.
- Qualify ALIGN-generated analog macros through the MPW pre-check, DRC, LVS,
  MDP, and RC/parasitic extraction flow.
- Fix the TR-1um ALIGN abstraction DRC debt (CO width/enclosure, V1
  enclosure/overlap, off-grid 0.050) in `layers.json`/`mos.py` so generated
  primitives pass the foundry drawing-layer DRC deck.

## Engineering RCX assumption log

The current RCX implementation is an engineering estimate because the open
IP62 collateral does not include a qualified parasitic-extraction deck. The
executable values are maintained in
`flow/scripts/analysis/tr1um_parasitic_model.json`; update that file and this
section together when new process documentation, foundry data, or silicon
correlation becomes available.

- **Baseline interconnect:** M1 uses 0.027777778 ohm/um and 0.163 fF/um;
  M2 uses 0.010000000 ohm/um and 0.1525 fF/um; reserved M3 uses
  0.010000000 ohm/um and 0.160 fF/um. These are derived from LEF sheet,
  area-capacitance, and edge-capacitance values. For each routed graph edge,
  `R = Rsheet * L / W` and `C = L * (Carea * W + 2 * Cedge)`, where `W` is
  the explicit DEF width or the nominal LEF width for widthless routes.
  +/-50% bands are engineering sensitivity ranges, not confidence intervals.
- **Via resistance:** V1 is 1.0 ohm nominal with a 0.5--2.0 ohm range because
  no via resistance is published.
- **Lateral coupling:** M1/M2/M3 use 0.00005 pF/um edge capacitance with
  exponential spacing attenuation: decay 1.8 um for M1, 3.0 um for M2/M3,
  and maximum modeled spacing 5.4 um for M1 or 9.0 um for M2/M3.
- **M1/M2 overlap coupling:** 0.0000175 pF/um2 from
  `vertical_coupling.M2_M1` is applied to axis-aligned DEF route
  bounding-box intersections. This is an engineering adjacent-metal proxy;
  no foundry inter-metal coupling coefficient is published.

- **M3 vertical coupling:** M3--M2 is 0.0000175 pF/um2; M3--M1 and
  M3--substrate are 0.000020 pF/um2. GDS overlap uses axis-aligned bounding
  boxes rather than polygon clipping or a field solve.
- **GR/F_RS:** 0.000615 pF/um2 is reused from the legacy CSIO coefficient;
  `C = density * W * L`, split equally over PLUS/MINUS. GR defaults to
  PSUB/VSS; overlap with WN classifies it as NW/VDD.
- **RR/F_RR and GC/MOS:** RR uses the checked-in `F_RR c_d0` PLUS--SUB
  expression, while GC uses BSIM3 `cgsl`/`cgdl` values of 1.81 fF/um for
  PMOS and 2.02 fF/um for NMOS. These are source-derived compact-model
  terms, not independent foundry measurements; avoid double counting them.
- **Geometry and hierarchy:** unlabelled M3 defaults to the configured
  substrate net, and only device terms resolved to selected top-level routed
  nets enter SPEF/SPICE. Nested devices remain ledger-only. No V2 route model
  or foundry-qualified substrate/inter-metal coefficient is assumed.

### Distributed PEX and OpenSTA path-class evidence

The corrected extractor emits version-3 distributed SPEF and SPICE RC
networks. Routed nets contain DEF/LEF `*CONN` records, graph nodes split at
route endpoints, vias, terminals, and same-net intersections, node-ground
capacitance records, lateral coupling records, M1/M2 overlap coupling, and
per-edge wire/via resistors. The adjacent JSON ledger records widths,
coordinates, topology, edge values, coupling basis, and warnings.

The post-layout runner passes a distributed SPEF directly to OpenSTA when
`*CONN` and graph-node records are present. Legacy SPEFs with empty `*CONN`
use the explicit `legacy_lumped_bridge` fallback, which collapses coupling
and replaces scalar net resistance with a star network. Direct runs report
`distributed_direct` and zero coupling collapse.

The six manifest-backed digital run artifacts were regenerated under their
ignored `flow/designs/*/runs/*/final/spef/` directories. Each run now has a
distributed `..spef`, `..pex.sp`, and `..parasitics.json` ledger. The FIFO
audit contains 5,485 graph nodes, 4,320 resistor edges, 1,693 ground-cap
records, 3,139 coupling pairs, and 12,275.38 um2 of M1/M2 overlap area.

OpenSTA path-class reciprocal-delay estimates from the regenerated SPEFs are:

| Design | Input -> output | Reg -> reg | Input -> reg | Reg -> output |
| --- | ---: | ---: | ---: | ---: |
| `tr1um_alu8` | n/a | n/a | 21.400 MHz (46.730 ns) | 119.531 MHz (8.366 ns) |
| `tr1um_fifo4` | n/a | 37.608 MHz (26.590 ns) | 62.500 MHz (16.000 ns) | 42.230 MHz (23.680 ns) |
| `tr1um_irqctrl` | 100.990 MHz (9.902 ns) | 56.370 MHz (17.740 ns) | 92.081 MHz (10.860 ns) | 63.532 MHz (15.740 ns) |
| `tr1um_spitx` | n/a | 36.778 MHz (27.190 ns) | 67.797 MHz (14.750 ns) | 58.207 MHz (17.180 ns) |
| `tr1um_busdecode` | n/a | n/a | 500.000 MHz (2.000 ns) | 64.309 MHz (15.550 ns) |
| `tr1um_uarttx_big` | n/a | 33.422 MHz (29.920 ns) | n/a | 31.279 MHz (31.970 ns) |

The table uses the audited single-corner Liberty generated by
`flow/char/char_liberty.py`: LEF-derived cell areas, ngspice input-charge
measurements, SPICE-derived delay/transition tables, and 5% DFF setup
push-out constraints. Hold arcs remain uncharacterized; DFFS CK-to-Q timing
still uses the DFFR electrical path pending SET-polarity reconciliation.

Rates use `f_MHz = 1000 / t_ns`, where `t_ns` is the OpenSTA endpoint data
arrival for that path class. Only `reg -> reg` is a synchronous-clock
candidate. These are engineering reciprocal-delay indicators, not signoff
Fmax values: setup, hold, skew, uncertainty, complete clock modeling, and
foundry-qualified parasitics are not included. The regenerated full runner
reported RTL and slow-view functional PASS for all six cases; strict timing
remained failing for five cases, so the overall status is
`PASS_WITH_TIMING_FAILURES`.

For the detailed flow contract and update procedure, see `flow/README.md`.

### Temperature model validation evidence

The checked-in temperature release contract now declares `27..85 degC`
operation, while retaining `25..150 degC` RS characterization and the
`-40..150 degC` manual MOS guarantee. This is a release-scope change; it does
not establish that the original `-40..85 degC` product requirement is safe.
`flow/scripts/signoff/run_temperature_validation.py` probes `27`, `85`, and
`150 degC` for `PMOS_mst`, `NMOS_mst`, `MPE_mst`, `MNE_mst`, `F_RR`, `F_RS`,
`DN`, and `DP`. The report is retained at
`flow/qualification/reports/temperature-validation/temperature_validation.json`.

All executable MOS, RR, RS, and diode probes pass. The contract marks RS
below-25 degC extrapolation `not_needed`; this removes that specific blocker.
`F_RS` remains a nominal-only warning because its source has `tnom=27` but no
`temper` term.

CSIO is also an explicit warning, not a blocker. The source has
`.model m_CSIO C tnom=27` but no `TC1`/`TC2` or other machine-readable
temperature law, so the report audits it statically and makes no measured
capacitance-vs-temperature claim. Ngspice documents `TC1`/`TC2` as the
capacitor temperature-correction inputs:
[capacitor syntax](https://nmg.gitlab.io/ngspice-manual/circuitelementsandmodels/elementarydevices/capacitors.html).
The report status is `PASS_WITH_WARNINGS`; the warnings are retained for
traceability rather than stopping the 27..85 degC validation. The separate
[F_CSIO runtime issue](https://github.com/OpenSUSI/TR-1um/issues/96) reports
voltage-domain convergence risk in the behavioral C2 expression.

## Foundry errata (IP62 rev 1.1)

All items below were reported and confirmed with Tokai Rika.

- DRC: full-custom layout is not supported except via parameterized cells
  (PCells); device recognition layers (DLXXXX) add complexity and risk; no
  off-grid/not-diagonal check (introduced in the new runset); no explicit
  NF/PF-to-PSUB requirement in the document (defined: PSUB = NF = PF); no
  explicit fat-M2 rule (defined: same as M1); no quantized W check for RR/RS
  even though the model allows only 2.8/4.0/6.0/12.0/20.0.
- PCell: CSIO generates off-grid CONT.
- LVS: RR/RS does not compare L/W values (L/W check introduced in the LVS
  runset).
- SPICE model: RR/RS model does not match the left-right parentheses count.
