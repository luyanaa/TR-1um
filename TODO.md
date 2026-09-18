# TODO for TR-1um signoff safety

This is the release-blocking checklist for the mixed-signal submission. A
clean local drawing/structural gate is not equivalent to signoff safety.
Completed checklist entries are removed; only unresolved work remains here.

## Scope and qualification boundaries

- [ ] Complete design-specific qualification for `CMC_S_NMOS_B_X1_Y1`:
  review guard structures, PG/return-path geometry, current envelope, and
  analog performance before calling the macro signoff-ready.
- [ ] Keep the `TELESCOPIC_OTA` handoff blocked until finalized, matching
  top-level GDS, LEF, CDL, and black-box views independently pass DRC and LVS.
  Do not substitute the current handoff metadata or black-box-only view.

## DRC, LVS, and top-level coverage

- [ ] Reconcile the DRC regression baseline after syncing upstream PR #18 from
  `OpenSUSI/TR-1um_DRC_Regression_TEST`. The complete LibreLane nix-shell run
  now covers all 432 cases and reports 292 passes and 140 baseline failures:
  Cat-1 25 passed/0 failed, Cat-2 67/0, Cat-3 65/0, Cat-4 78/1,
  Cat-5 0/47, Cat-6 27/23, Cat-7 0/39, and Cat-8 30/30. Do not mask or
  waive these results; the remaining failures stay review items until the
  active runset and fixture expectations are reconciled.

## Electrical, timing, and corner analysis

- [ ] Close PDNSim power-integrity analysis: provide qualified EM/IR limits,
  explicit VDD/VSS source locations, macro PG geometry, worst-case activity
  current envelopes, metal/via limits, and a separate GND return-path result.
  Current engineering-only evidence is in
  `flow/qualification/reports/pdn-emir/pdn_emir.json`; it records the
  post-streamout bridge estimate and digital-design connectivity failures but
  does not close IR/EM or ground-bounce signoff.
- [ ] Audit ESD integration at the hierarchy boundary. The structural gates
  pass for the analog macro's GDS/LEF/CDL/black-box view contract, framed
  ERC/body-tie evidence, and strict LVS/netlist-label reports. The pad-level
  ESD checker remains `BLOCKED` because no per-pad positive/negative discharge
  map, package assumptions, or qualified limits are bundled.
- [ ] Audit `GND_BRIDGE` integration in the final GDS, DEF, LEF/CDL, and LVS
  views. The canonical post-streamout GDS contains exactly one 3.0 um M2
  bridge from the top-level GND label to the macro GND landing and a separate
  `ANA_DB` detour; measured minimum bridge-to-analog clearance is 2.4 um,
  above the 2.0 um M2 spacing rule, and the strict LVS/ERC evidence passes.
  The bridge is GDS-only while the canonical DEF has logical GND connectivity
  but no GND route, and LVS normalizes GND to VSS. Keep the VSS-only return,
  substrate continuity, and IR/EM claims blocked until that alias and
  package/pad-ring contract is independently qualified.
- [ ] Add RF validation for any RF-relevant path: define S-parameter, gain,
  noise, linearity, stability, loading, and matching measurements with
  extracted parasitics across the declared voltage, temperature, and process
  corners.

## Analog and physical robustness

- [ ] Instantiate the post-layout flow with real extracted decks and valid
  signoff views. The current manifest remains blocked because foundry-qualified
  analog extraction/models and matching OTA views are absent.
- [ ] Instantiate crosstalk analysis for every sensitive analog victim,
  including clock, digital, supply/ground, neighboring M1/M2, and frame-M3
  aggressors, with design-specific limits and measured glitch/settling/delay
  evidence.
- [ ] Instantiate mismatch and overdesign review for every precision group.
  Provide process sigma data or a reviewed guardband, plus layout, headroom,
  current-density, and area evidence.
- [ ] Instantiate pad-level ESD review for every external pad with
  package-qualified limits and complete view-to-view discharge-path evidence.
- [ ] Instantiate capacitance review for all used MOS and capacitor devices.
  Bundle independent area/perimeter and value tables across voltage,
  temperature, and process corners.

## Release evidence

- [ ] Bundle the remaining exact framed GDS, matching DEF, routed netlist,
  LEF/CDL/black boxes, PVT corner inputs, SPICE decks/waveforms, M3 audit,
  analog reviews, tool versions, assumptions, and residual-risk decisions.
  The exact framed DRC/ERC/LVS and post-MDP report bundle is already listed in
  `flow/qualification/analog_signoff_manifest.json`.
- [ ] Keep `release_status: blocked` until all required stages close, all
  unresolved TODOs above are addressed, and every release artifact is
  independently traceable to the final framed revision.

## Analog primitive and extraction roadmap

This is planned analog-library work. It does not imply process-qualified
models, silicon correlation, or tapeout readiness.

### A. Analog primitive library

- [ ] Define the analog primitive library contract.
- [ ] Implement an NMOS primitive.
- [ ] Implement a PMOS primitive.
- [ ] Implement an NMOS pair.
- [ ] Implement a PMOS pair.
- [ ] Implement a common-centroid NMOS pair.
- [ ] Implement a common-centroid PMOS pair.
- [ ] Implement a current-mirror primitive.
- [ ] Implement a cascode-pair primitive.
- [ ] Implement a resistor primitive.
- [ ] Implement a capacitor primitive.
- [ ] Implement a diode primitive.
- [ ] Implement a guard-ring primitive.
- [ ] Implement substrate and well taps.

### B. Analog PEX

- [ ] Build a DEF-to-layout-driven PEX engine.
- [ ] Build the GDS conductor-connectivity graph.
- [ ] Map device terminals to conductor polygons.
- [ ] Extract terminal mapping from KLayout LVS.
- [ ] Merge the PEX deck with SPICE output.
- [ ] Couple devices with extracted interconnect.
- [ ] Build a shape-aware resistor mesh/field/current solver.
- [ ] Retain the compact resistor model for digital and fast emulation.
- [ ] Make CO cut arrays explicit.
- [ ] Make V1 cut arrays explicit.
- [ ] Extract a capacitance-matrix model.
- [ ] Build the substrate and well network.
- [ ] Solve RF inductance and frequency dependence.

### C. Local mismatch simulation

- [ ] Add paper-based local mismatch simulation.
- [ ] Model sigma(VTH) variation.
- [ ] Model sigma(beta)/beta variation.
- [ ] Add spatial correlation modeling.
- [ ] Plan future mismatch calibration.

### D. Layout-aware matching generator

- [ ] Build a layout-aware matching generator.

### E. Guard ring, substrate, and latch-up

- [ ] Generate guard rings from analog macros.
- [ ] Generate substrate networks from analog macros.
- [ ] Generate latch-up structures from analog macros.

### F. RC calibration

- [ ] Calibrate resistor extraction models.
- [ ] Calibrate capacitor extraction models.

### G. RF passives

- [ ] Build an inductor primitive.
- [ ] Build a spiral-inductor model.
- [ ] Build a transmission-line primitive.
- [ ] Build a transmission-line S-parameter model.

### H. RF transistor validation

- [ ] Validate RF transistor Y/S parameters.
- [ ] Add RF S-parameter simulation.
- [ ] Add S-parameter de-embedding.

### I. EM and distributed interconnect

- [ ] Build an EM/distributed-interconnect solver.
