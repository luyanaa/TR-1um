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
- Sweep the Ohno post-layout `RPEX/CPEX` network directly, then regenerate it
  from pinned DEF/RCX provenance while varying sheet/via resistance, wire
  capacitance, and lateral/vertical coupling independently; keep
  `C_residual,effective` separate from RCX and calibrate output-device
  headroom independently.
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

### Ohno OPAMP silicon anchor

- **Source:** The supplied `147307.pdf` I/O magazine issue, printed pages 25--28
  (local review copy: `~/Downloads/147307.pdf`). The article is a silicon review
  of the Shuntaro/Ohno custom OPAMP.
- **Bias-current anchor:** The schematic targets `I_B = 11.8 uA`, supplied by
  an external current sink. The article's discrete bias source is approximately
  `1.15 V / 100 kohm = 11.5 uA`; these are a design target and an approximate
  bench value, not the same precision measurement.
- **Silicon follower anchor:** At `1 Vpp`, the output follows at about 160 kHz
  and collapses at about 200 kHz. At `2 Vpp`, it follows at about 80 kHz and
  collapses at about 100 kHz. These observations bound the effective
  measurement-plane slew requirement as
  `0.503 <= S_silicon <= 0.628 V/us` (the upper bound is the 200 kHz/1 Vpp
  or 100 kHz/2 Vpp onset). This is not a single intrinsic `SR` value:
  oscilloscope-probe, pad, board, fixture, and model-current effects cannot
  be de-embedded from the magazine data.
  Do not treat this interval as a direct RCX capacitance measurement.
- **Bias/slew evidence:** The article reports that increasing the external bias
  current restores the distorted `2 Vpp` inverting waveform. Direct simulation
  of the current post-layout deck shows the same transition: nominal
  `11.8 uA` distorts the `10 kHz`, `2 Vpp` inverter, while `20 uA` restores
  approximately unity inversion. This is evidence for a bias/output-drive
  limitation, not only a fixed RC pole.
- **Compensation capacitor:** The Ohno netlist contains the explicit
  `C_C = 8.856 pF` element (`C$52`, output to the compensation node). Direct
  branch-current probing recovers approximately `8.8 pF` from its transient
  current and voltage slope.
- **Residual-effective capacitance bookkeeping:** If the pass boundary
  `0.503 V/us` is used only as a bookkeeping reference, the two silicon pass
  points imply `C_eff ~= 120.2--121.0 pF`. Using the onset bound
  `0.628 V/us` instead gives roughly `C_eff ~= 96.2--96.8 pF`. Thus
  subtracting the explicit `8.856 pF` and the `100 pF` simulation capacitor
  gives either `C_residual,effective ~= 11.3--12.1 pF` or approximately
  `-12.7 to -12.1 pF`; neither is a measured silicon capacitance. This is
  conditional bookkeeping, not a wire-capacitance estimate, not a foundry
  RC correction, and not the RCX calibration target.
  `C_residual,effective` may combine on-chip RCX, pad, bond, PCB, probe,
  fixture, and device-model current error. The magazine specifies an
  oscilloscope but does not specify a `100 pF` silicon output load.
- **Output-headroom anchor:** The measured follower clips near `4.6 V` from a
  `5 V` supply. The current post-layout model gives `Vout,max ~= 4.872 V` with
  or without its `100 pF` bench capacitor, and bias changes move this only
  slightly. This points to intrinsic model/device parameters (`V_TH`,
  `mu*g_ds`, `V_DS,sat`, and related output-stage headroom), not RCX. Do not
  tune RCX to force the model to `4.6 V`.
- **First direct RCX sensitivity sweep:** With the device model and `100 pF`
  fixture fixed, scaling every `RPEX` value from `0.25x` to `4x` changed the
  anchor tracking error by at most about `1.3 mV`; these silicon anchors do
  not identify wire/via resistance. Scaling every `CPEX` value from `0.05x`
  to `2x` strongly moved the pass/fail boundary. Retain the result as
  `$k_{C,\mathrm{coupling}}^{\mathrm{Ohno,conditional}}\approx0.8\text{--}1.2$`,
  where `conditional` means the current device model, current fixture
  assumption, and current `I_B` assumption. This is a conditional
  consistency range, not a global RCX accuracy or fitted calibration.
- **RCX component sensitivity:** Scaling only ground-capacitance entries by
  `0.5x--2x` barely moves the pass anchors (`44.4--46.5 mV` at `160 kHz`,
  `1 Vpp`). Scaling coupling entries by the same range moves that error from
  `35.2 mV` to `178 mV` and moves the `200 kHz`, `1 Vpp` failure error from
  `238 mV` to `586 mV`; output-associated capacitances are intermediate.
  The first calibration candidate is therefore lateral/vertical coupling,
  not an inferred wire-capacitance residual.
- **Joint nuisance sweep:** To avoid assigning the fixture or bias error to
  coupling, a `3 x 5 x 3` grid was run over
  `k_C,coupling={0.8,1.0,1.2}`, `C_fixture={50,70,100,130,150} pF`, and
  `I_B={11.50,11.65,11.80} uA` for five follower/inverter anchors
  (`225` ngspice runs). The requested pair
  `(1.0x,70 pF)` versus `(0.8x,100 pF)` is close at the low-frequency
  follower anchors (tracking-error differences `7.1` and `2.6 mV`) but is
  not globally interchangeable: the `200 kHz` and `100 kHz` failure
  anchors differ by `295.6` and `227.2 mV`. A different nearby pair,
  `(0.8x,70 pF,11.65 uA)` versus `(1.2x,50 pF,11.80 uA)`, keeps all four
  follower tracking errors within `2.8 mV` while the inverter differs by
  `15.8 mV`; this is explicit coupling/fixture/bias confounding. Do not fit
  a unique 3-D point. `100 pF` remains a simulation fixture nuisance value,
  not a proven silicon load, and `I_B` remains a nuisance parameter around
  the actual `~11.5 uA` rather than a fixed design target.
- **TR10-1 VCO cross-check (completed):** The canonical post-layout
  testbench is
  `analysis/tr10_rcx_vco/remediated/vco/vco.canonical.tb.sp` and the
  reproducible coupling sweep is
  `analysis/tr10_rcx_vco/run_coupling_crosscheck.py`. It uses
  `VDD=5 V`, `VCTRLN=VCTRLP=2.5 V`, no Ohno `100 pF` fixture, and a
  `10 ns/25 us uic` transient. The controlled pre-layout reference remains
  `period=1.34196 us`, `frequency=745.178 kHz`; it is a simulation reference,
  not a silicon measurement.
- The source-level VCO re-extraction exposed `30` top-terminal attachments
  emitted as ideal `0 ohm` `RPEX` edges. The extractor now emits an explicit
  `1e-6 ohm` numerical floor for those topological attachments, records that
  floor in the ledger, and preserves the physical RC ownership. The repaired
  deck has no zero-valued `RPEX` entries.
- The repaired post-layout baseline converges with `2657` transient rows:
  `period=1.40073 us`, `frequency=713.915 kHz`, and
  `Vout=-12.6 mV..5.024 V`. Relative to the controlled pre-layout reference,
  this is a `-4.20%` frequency shift; it is not a silicon reverse-inference
  result.
- The coupling-factor cross-check scales only the `309` non-ground `CPEX`
  entries while preserving the `60` `VSS` ground entries (`369` total).
  Results are `717.519 kHz` at `0.8x`, `713.916 kHz` at `1.0x`, and
  `709.765 kHz` at `1.2x`, with all three runs producing valid `.meas`
  output. The full logs, decks, ledgers, and manifest are under
  `analysis/tr10_rcx_vco/remediated/vco/`.
- The VCO ledger still uses the reduced
  `tr1um_parasitic_model_no_lateral.json`; lateral-coupling sensitivity,
  foundry-qualified RCX, and calibrated oscillator device parameters remain
  unresolved. Report this sweep as engineering-model sensitivity, not as
  measured silicon calibration.
- **Remaining validation step:** Replace the reduced engineering RC model and
  synthetic/reference extraction inputs with foundry-qualified VCO RCX,
  compact-model ownership, and LVS-clean analog views before using the VCO
  frequency for quantitative silicon inference. Use the silicon data only as
  qualitative ordering/region constraints; calibrate output-device headroom
  separately.

### TR10-1 original-model no-PEX calibration snapshot

The previous `k_C,ring=8` result is withdrawn as a physical VCO
calibration. It was a useful sensitivity experiment on the repaired
post-layout deck, but it is not required by the original-model,
no-PEX reference below and may have absorbed model-version and control-point
differences.

- **PDK snapshot:** ISHI-KAI
  `OpenRule1umPDK_setupEDA@f8862f775cad` (2024-09-26), the initial TR10
  model snapshot that retains the schematic names `nchor1ex` and
  `pchor1ex`. The current HEAD model rename is not used for this reference.
- **MOS model:** the original `nchor1ex`/`pchor1ex` level-8 model from
  `xschem/lib/TR10/mos.lib`; no calibrated `PMOS_mst`/`NMOS_mst` overlay.
- **Poly-metal capacitor:** the original
  `xschem/lib/TR10/passive.lib` model is
  `poly_cap`, with `cox=3.06e-15 F/um^2`, `tc1=tc2=0`, and `capsw=0`.
  The schematic convention is numeric `W=20`, `L=20` in micrometres
  (not `20u` SPICE lengths), giving
  `3.06 fF/um^2 * 20 um * 20 um = 1.224 pF` per ring node.
- **Original VCO geometry:** seven ring capacitors; inverter devices
  `PMOS W/L=3/1 um`, `NMOS W/L=2/1 um`, current-limiter devices
  `PMOS W/L=12/10 um` and `NMOS W/L=4/10 um`; the inverter control
  devices retain `PMOS W/L=12/5 um` and `NMOS W/L=8/5 um`.
  The buffer uses the original `PMOS W/L=3/1 um`, `NMOS W/L=2/1 um`
  pair.
- **No-PEX boundary:** the source-level VCO device netlist is used without
  `XPEX`, wire capacitance, lateral coupling, or wire/via resistance.
  Intrinsic MOS capacitances and the source/drain geometry fields remain
  part of the original MOS model. The reproducibility record is
  `analysis/tr10_rcx_vco/nopex_original/manifest.json`.
- **Original test point:** `sim_vco.sch` specifies `VDD=5 V` and
  `VCTRL=5 V`, with no external output capacitor.

#### No-PEX result

- At the original `VDD=5 V`, `VCTRL=5 V`, the no-PEX deck shows no
  measurable oscillation during `1 ns/200 us uic`; the output remains
  approximately `1.24 uV`. Therefore the original 5 V control point does
  not reproduce the 100 kHz target in this model.
- Keeping the same original MOS model, geometry, and `poly_cap` value,
  but sweeping only the ideal control source, gives
  `f=98.7341 kHz` at `VCTRL=3.50 V`
  (`T=10.1282 us`, `Vout=-30.9 uV..5.00137 V`).
- Replacing each model-form capacitor
  `poly_cap W=20 L=20` with an explicit `1.224 pF` capacitor gives the
  same `98.7341 kHz` result at `VCTRL=3.50 V`. The factor-of-eight
  capacitance multiplier is therefore not needed to reconcile the
  original capacitor model with the original no-PEX VCO.

**Calibration decision:** retain `k_C,coupling=0.8`, `C_fixture=70 pF`,
and `I_B=11.65 uA` as the conditional TR10-2/Ohno measurement-plane
candidate. For TR10-1, set `k_C,ring=1.0` in the original-model/no-PEX
reference. Do not use `k_C,ring=8` as a foundry-RCX or intentional-capacitor
correction. Reconciling the measured 5 V-control behavior now belongs to
the VCTRL/current operating point, model-version mapping, and measurement
loading—not to an automatic eightfold increase of the ring capacitor.

### Historical-model VCTRL=3.5 V with distributed PEX

To test whether the observed `33 kHz`/`100 kHz` split can be caused by
layout parasitics, the original-model/no-PEX deck was augmented with the
repaired engineering `tr1um_parasitics` network from
`analysis/tr10_rcx_vco/remediated/vco/vco.post.sp`. The historical
`nchor1ex`/`pchor1ex` models, original source-level W/L, and seven
`1.224 pF` intentional capacitors were retained. `RPEX` and the intentional
`CLEG` capacitors were unchanged; only `CPEX` was scaled for sensitivity.
The primary hybrid connects the parasitic substrate to the VCO `P30` VSS
pin. The emitted `VSS` connection was also tested separately.

- The no-PEX reference is `98.7341 kHz` at `VCTRL=3.50 V`.
- The checked-in engineering PEX has `1.52988 pF` total `CPEX`. At
  `CPEX=1.0x`, it gives `95.7507 kHz` at `VCTRL=3.50 V`, a `-3.02%`
  shift, not `33 kHz`.
- Keeping the emitted `VSS` connection instead of `P30` gives
  `95.9993 kHz`; this `0.26%` difference cannot explain the observed
  frequency split.
- The scale-1 control sweep remains operational around 100 kHz:
  `VCTRL=3.48 V -> 107.273 kHz`,
  `3.49 V -> 101.420 kHz`,
  `3.50 V -> 95.751 kHz`, and
  `3.52 V -> 84.985 kHz`.
- Scaling only the engineering `CPEX` gives
  `CPEX=2x -> 93.2853 kHz`,
  `4x -> 89.7754 kHz`,
  `8x -> 84.6416 kHz`,
  `16x -> 76.8258 kHz`,
  `32x -> 65.5869 kHz`, and
  `64x -> 50.5549 kHz`. At `128x` the output collapses and no valid
  oscillation remains; no stable `33 kHz` point is reached.

**Conclusion:** the extracted engineering parasitic network does not
reproduce `33 kHz` at the current `VCTRL=3.5 V`, and it does not make
`100 kHz` unavailable—`VCTRL=3.49 V` still produces `101.420 kHz`.
Forcing the result toward `33 kHz` would require an unsupported, very large
increase of the extracted `CPEX` rather than the measured network. Do not
turn that sensitivity factor into a physical RCX or `k_C,ring` correction.
The reproducible hybrid builder, decks, logs, and limitations are recorded
under `analysis/tr10_rcx_vco/nopex_original/pex_hybrid/manifest.json`.

### Model-library scope across TR10 analyses

The historical ISHI-KAI `f8862f775cad` library is **not** a global
replacement for the model set used by the other circuit studies.

- The TR10-1 VCO no-PEX reference is the one case that explicitly uses the
  historical `nchor1ex`/`pchor1ex` MOS and `poly_cap` definitions, because
  those names and the original capacitor convention are present in the
  source-level TR10-1 VCO deck.
- The Ohno/OPAMP post-layout studies use the OS00-calibrated
  `ip62_models_calibrated` bundle. Their
  `k_C,coupling`, fixture-capacitance, and bias-current results are
  conditional on that device model; changing the MOS library requires
  rerunning and refitting the nuisance sweep, not relabeling the old
  results.
- The TR10-1 inverter and DCDC studies are schematic-level surrogates that
  use `flow/char/fixed_models.sp`, which supplies the calibrated
  `PMOS`/`NMOS`, capacitor, diode, and resistor model interfaces. The
  original DCDC `mos.lib`/`passive.lib`/`diode.lib` wrappers and exact
  source netlist are not present in the extracted project, so replacing
  only the MOS file with the historical VCO library would not be a valid
  correction.

**Decision:** do not retroactively replace the other circuit libraries.
Keep their results labeled as calibrated/surrogate analyses. If
cross-circuit model consistency becomes necessary, run a paired baseline
with both model sets for each circuit and refit its own measurement-plane
parameters; do not transfer `k_C,ring`, `k_C,coupling`, or load corrections
between circuits.

### Impact on previously corrected parameters

The historical-model VCO check changes the scope of the corrections, not
the numerical values of the other circuit-specific results.

- **Withdraw:** `k_C,ring=8` for TR10-1. Use `k_C,ring=1.0` in the
  original-model/no-PEX reference. Do not apply this factor to OPAMP,
  inverter, or DCDC analyses.
- **Keep unchanged:** `poly_cap=3.06 fF/um^2`,
  `1.224 pF` per intentional VCO ring capacitor, and the seven-stage
  `8.568 pF` total. The model-form and explicit-capacitance checks agree.
- **Keep, but conditional:** the Ohno/OPAMP
  `k_C,coupling=0.8--1.2`, `C_fixture=50--150 pF` sweep, and
  `I_B=11.50--11.80 uA` nuisance range remain tied to
  `ip62_models_calibrated`. They are not invalidated by the VCO library
  check; changing the OPAMP device library would require refitting them.
- **Do not recalibrate yet:** the reduced VCO PEX coefficients and
  `tr1um_parasitic_model_no_lateral.json` remain engineering proxies. The
  VCO PEX experiment showed only a `98.7341 -> 95.7507 kHz` shift at the
  extracted `CPEX=1.0x`; it provides no evidence for multiplying PEX or
  intentional capacitance.
- **Separate surrogate assumptions:** DCDC/inverter load capacitance,
  input waveform, inductor, and output-capacitor values are testbench
  assumptions, not transferable device-library corrections.

Therefore the only prior correction that is numerically revoked is the
TR10-1 VCO `k_C,ring=8` factor. The other parameters remain valid within
their stated model and measurement-plane scope.

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

OpenSTA path-class reciprocal-delay estimates from the refreshed six-case
post-layout run are:

| Design | Input -> output | Reg -> reg | Input -> reg | Reg -> output |
| --- | ---: | ---: | ---: | ---: |
| `tr1um_alu8` | n/a | n/a | 18.406 MHz (54.330 ns) | 113.507 MHz (8.810 ns) |
| `tr1um_fifo4` | n/a | 32.103 MHz (31.150 ns) | 54.171 MHz (18.460 ns) | 38.880 MHz (25.720 ns) |
| `tr1um_irqctrl` | 99.010 MHz (10.100 ns) | 53.191 MHz (18.800 ns) | 86.207 MHz (11.600 ns) | 60.976 MHz (16.400 ns) |
| `tr1um_spitx` | n/a | 34.235 MHz (29.210 ns) | 60.864 MHz (16.430 ns) | 54.171 MHz (18.460 ns) |
| `tr1um_busdecode` | n/a | n/a | 500.000 MHz (2.000 ns) | 60.350 MHz (16.570 ns) |
| `tr1um_uarttx_big` | n/a | 31.192 MHz (32.060 ns) | n/a | 28.169 MHz (35.500 ns) |

The table uses the audited single-corner Liberty generated by
`flow/char/char_liberty.py`: LEF-derived cell areas, ngspice input-charge
measurements, and SPICE-derived NLDM delay/transition tables for every
standard cell on the 0.5/1/2/5/10/15/20 ns input-transition by 0.1/0.5/2.0 pF
load grid. Sequential constraints use 5% clock-to-Q push-out searches for setup,
hold, recovery, and removal. DFFR and DFFS CK-to-Q timing use their own
extracted electrical paths; the extracted DFFS SET path is active-low and is
encoded with Liberty `preset_polarity : "N"`.

Rates use `f_MHz = 1000 / t_ns`, where `t_ns` is the OpenSTA endpoint data
arrival for that path class. Only `reg -> reg` is a synchronous-clock
candidate. These are engineering reciprocal-delay indicators, not signoff
Fmax values: setup, hold, skew, uncertainty, complete clock modeling, and
qualified parasitics are not represented by reciprocal delay alone.

The refreshed OpenSTA check metrics are:

| Design | Setup WNS (ns) | Setup TNS (ns) | Hold WNS (ns) | Hold TNS (ns) | Max slew violations | Max cap violations | Max fanout violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `tr1um_alu8` | 4941.348 | 0.000 | 4.965 | 0.000 | 0 | 0 | 1 |
| `tr1um_fifo4` | 4964.451 | 0.000 | 2.443 | 0.000 | 0 | 0 | 1 |
| `tr1um_irqctrl` | 4976.812 | 0.000 | 3.022 | 0.000 | 0 | 0 | 0 |
| `tr1um_spitx` | 4966.370 | 0.000 | 2.443 | 0.000 | 0 | 0 | 0 |
| `tr1um_busdecode` | 4979.434 | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 |
| `tr1um_uarttx_big` | 4960.505 | 0.000 | 7.737 | 0.000 | 0 | 0 | 2 |

WNS/TNS are OpenSTA `worst_slack` and `total_negative_slack` for max
(setup) and min (hold) paths, in ns. Slew, capacitance, and fanout columns
count violating rows from `report_check_types`; the extra fanout column
explains the remaining nonzero design-rule violations. The runner summary
was `execution_status: PASS`, `functional_status: PASS`, and
`strict_timing_status: FAIL` (`PASS_WITH_TIMING_FAILURES`). The complete
physical-flow regression was not rerun.

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
