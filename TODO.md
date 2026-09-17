# TODO for TR-1um signoff safety

This is the release-blocking checklist for the mixed-signal submission. A
clean local drawing/structural gate is not equivalent to signoff safety.
Completed checklist entries are removed; only unresolved work remains here.

## Scope and qualification boundaries

- [ ] Replace the engineering M3 bound with reviewed foundry or silicon
  correlation before treating M3 RCX as qualified.
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

## Electrical, timing, and corner analysis

- [ ] Run OpenSTA using the matching RCX SPEF extraction and routed netlist.
  Report setup/hold, slew, capacitance, fanout, clock skew, recovery/removal,
  generated clocks, and unconstrained endpoints for every declared corner.
- [ ] Complete PDNSim power-integrity analysis: EM limits, IR-drop limits,
  VDD/VSS source definitions, macro PG geometry, current envelopes, worst-case
  activity, metal/via limits, and a separate GND return-path result.
- [ ] Audit ESD integration at the hierarchy boundary. Resolve whether every
  ESD element must be a hard macro with a matching LEF, GDS, CDL, and
  black-box view, and verify placement in the pad ring or at the
  digital/analog boundary with package-qualified discharge paths.
- [ ] Audit `GND_BRIDGE` integration in the final GDS, DEF, LEF/CDL, and LVS
  views. Verify its pad-ring or digital/analog-boundary placement, VSS-only
  intent, substrate/tap continuity, return-current path, spacing to analog
  nets, and absence of an unintended short to `ANA_DB` or other signals.
- [ ] Complete temperature validation for every used device over the declared
  `-40..85 degC` operating range, including low-temperature RS evidence and
  model/manual reference-temperature reconciliation.
- [ ] Add RF validation for any RF-relevant path: define S-parameter, gain,
  noise, linearity, stability, loading, and matching measurements with
  extracted parasitics across the declared voltage, temperature, and process
  corners.
- [ ] Run a synthetic PVT sweep covering Fast Corner, Slow Corner, and Cross
  Corner combinations (`FF`, `SS`, `FS`, and `SF`) with explicit model,
  Liberty, RCX, supply, and temperature provenance.
- [ ] Run pseudo-Monte Carlo analysis on model parameters `V_th`, `mu_0`
  (`μ₀`), and `R_sq` (`Rₛq`). Declare distributions, correlation assumptions,
  sample count, seeds, measured outputs, acceptance limits, and tail metrics.
- [ ] Run sensitivity analysis for process, device, interconnect, supply, and
  temperature parameters. Rank their effects on timing, current, voltage
  margin, analog operating points, RF metrics, and return-path integrity.

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
