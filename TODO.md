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

- [ ] Reconcile the current 399-case DRC regression baseline before claiming
  complete DRC coverage. Deliberately track the 161 mismatches as unresolved
  TODO rather than masking or waiving them: Cat-4 has 22, Cat-5 has 47,
  Cat-6 has 23, Cat-7 has 39, and Cat-8 has 30. Do not describe the regression
  as clean until these mismatches are resolved or separately justified.
- [ ] Refresh the LVS tutorial examples before presenting the manual as
  current. The links resolve, but the parity review still records four
  semantic-drift warnings and one reference-only combiner contract.
- [ ] Add a top-level connectivity check based on
  `TR-1um_MPW_template/scripts/pre_check.py`. Extend the frame/name/dbu/bbox
  checks with explicit pad, rail, port, frame-cell, and net-to-pin
  connectivity checks against the final GDS, DEF, and routed netlist.

## IP62 errata carry-over

- [ ] Resolve the `CSIO` PCell off-grid `CONT` erratum. Ensure generated
  contacts stay on the 50 nm grid for every supported parameter set, and
  demonstrate the result with a KLayout DRC check.
- [ ] Correct the `F_RR` and `F_RS` compact-model left/right parenthesis-count
  mismatch. Validate every supported resistor-width branch with an ngspice
  parse and runtime smoke test before release.


## Electrical, timing, and corner analysis

- [ ] Close PDNSim power-integrity analysis: provide qualified EM/IR limits,
  explicit VDD/VSS source locations, macro PG geometry, worst-case activity
  current envelopes, metal/via limits, and a separate GND return-path result.
  Current engineering-only evidence is in
  `flow/qualification/reports/pdn-emir/pdn_emir.json`; it records the
  post-streamout bridge estimate and digital-design connectivity failures but
  does not close IR/EM or ground-bounce signoff.
- [ ] Audit ESD integration at the hierarchy boundary. Resolve whether every
  ESD element must be a hard macro with a matching LEF, GDS, CDL, and
  black-box view, and verify placement in the pad ring or at the
  digital/analog boundary with package-qualified discharge paths.
- [ ] Audit `GND_BRIDGE` integration in the final GDS, DEF, LEF/CDL, and LVS
  views. Verify its pad-ring or digital/analog-boundary placement, VSS-only
  intent, substrate/tap continuity, return-current path, spacing to analog
  nets, and absence of an unintended short to `ANA_DB` or other signals.
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
