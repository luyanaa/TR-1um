## Script organization

Flow utilities are grouped by purpose under `flow/scripts/`:

- `common/`: shared shell helpers used by flow launchers.
- `align/`: ALIGN execution, GDS post-processing, and macro signoff.
- `access/`: IP62 BEOL access-library generation and qualification.
- `cells/`: immutable source-cell view preparation and qualification.
- `signoff/`: MPW framing, pre-checks, DRC/LVS/MDP checks, and tapeout gates.
- `analysis/`: RC estimation, PVT/model variation, and bounded sensitivity analysis.

The three top-level LibreLane launchers share setup and argument handling from
`flow/scripts/common/librelane.sh`; they differ only in the selected standard
cell library. There are no compatibility copies in the old flat directory.

# TR-1um LibreLane flow integration (flow-only, STDLIB untouched)

Status: LibreLane Classic PnR and ALIGN macro integration for the OpenSUSI
TR-1um drawing-layer PDK. The native IP62 standard-cell path and the opt-in
access-cell experiment are intentionally separate from the ALIGN analog macro
path.

## Digital/analog library boundary

The default LibreLane digital library is the original IP62/STDLIB library,
`TR-1um_stdcell`. ALIGN-generated standard-cell collateral is not used by the
digital flow; ALIGN remains applicable to separately integrated analog macros.
IP62 cells provide the digital PnR collateral: LEF, GDS, Liberty, Verilog,
SPICE/CDL, fixed row height, and digital pin/rail geometry. ALIGN generates
analog-aware cells from transistor netlists and primitive PDK generators; its
output does not share the IP62 row, pin-access, or abutment contract.

The two flows share only the stable top-level contracts: TR-1um layer names,
database units, manufacturing grid, power names, and LVS pin names. Digital
SDC/PDN/placement constraints and analog ALIGN constraints remain separate at
the macro boundary.

## Mixed-signal hard-leaf integration

The analog boundary uses fixed TR-1um PCell-generated hard leaves. ALIGN's
transistor generator remains useful for discovering primitive topology, but its
abstract 7 µm contact grid cannot express the foundry's legal FEOL contact
geometry. The hard-leaf flow therefore separates topology from physical leaf
generation:

```mermaid
flowchart LR
    accTitle: Analog hard-leaf integration
    accDescr: A TR-1um PCell leaf is qualified, converted to ALIGN collateral, and consumed by LibreLane as a fixed mixed-signal macro.
    netlist[ALIGN primitive contract] --> pcell[TR-1um PCell leaf]
    pcell --> labeled[GDS with pin labels]
    labeled --> checks[Drawing DRC and strict LVS]
    checks --> lef[ALIGN/OpenROAD LEF]
    lef --> macro[LibreLane MACROS entry]
    macro --> top[mixed-signal top level]
```

### Verified composite leaf

`CMC_S_NMOS_B_X1_Y1` was checked with the contract:

```text
.SUBCKT CMC_S_NMOS_B_X1_Y1 G DA SA DB SB B
M1 DA G SA B NMOS L=1U W=3.4U
M2 DB G SB B NMOS L=1U W=3.4U
.ENDS CMC_S_NMOS_B_X1_Y1
```

The final composite GDS has two independently legal NMOS leaves, a physical
shared-gate M1 bridge, separate `DA`, `DB`, `SA`, and `SB` contacts, and a
shared body net. Verified results:

| Check | Result |
|---|---|
| TR-1um drawing DRC | 0 items |
| Strict LVS | Netlists match |
| ALIGN black-box conversion | PASS |
| Extracted pin order | `G DA SA DB SB B` |

The converted LEF uses explicit `M1` pin rectangles and is stored as
`flow/align_macro/CMC_S_NMOS_B_X1_Y1.lef`. The macro LEF uses canonical LEF
global units and micron-valued geometry; this is required by OpenROAD.

### Mixed-signal counter smoke and signoff route

The mixed-signal template is under `flow/designs/tr1um_mixed_counter/`. It
combines the four-bit digital counter with the fixed analog hard macro.

The reproducible signoff configuration is:

```text
flow/designs/tr1um_mixed_counter/config_access.yaml
flow/designs/tr1um_mixed_counter/constraints.sdc
flow/designs/tr1um_mixed_counter/manual_place_access.tcl
flow/designs/tr1um_mixed_counter/src/tr1um_mixed_counter.v
```

From a local LibreLane checkout, enter its development shell before running
the flow. The launcher supplies the repository-local PDK root and selected
SCL; no Nix store path needs to be copied into the project documentation:

```bash
cd "$HOME/Documents/librelane"
nix-shell
cd "$HOME/Documents/TR-1um"
./flow/run_librelane_tr1um_access.sh \
  flow/designs/tr1um_mixed_counter/config_access.yaml \
  --run-tag gc-diode-repair13
```

The access flow uses a single declarative macro placement at `(300,300)`;
the deprecated `MACRO_PLACEMENT_CFG` path is deliberately absent. The
access-cell detailed-placement mirroring pass is disabled because vertically
flipped access cells create AP row-boundary DRC errors. `RUN_PDN` remains
disabled because this analog macro has no full power-grid shape/via set; its
GND escape is routed as a deterministic special route after detailed routing.
The disconnected-pin checker remains enabled and must report zero.

The final repaired routed run is:

```text
flow/designs/tr1um_mixed_counter/runs/gc-diode-repair13
```

The analog macro escape-ring collateral is generated by
`flow/scripts/signoff/gen_macro_beol_access.py`. Because it uses KLayout's
`pya` runtime, invoke the checked-in wrapper from the local LibreLane
`nix-shell` rather than invoking a system Python interpreter:

```bash
cd "$HOME/Documents/librelane"
nix-shell
cd "$HOME/Documents/TR-1um"
python3 flow/scripts/signoff/run_macro_beol_access.py \
  --input flow/align_macro/CMC_S_NMOS_B_X1_Y1.source.gds \
  --output-gds flow/align_macro/CMC_S_NMOS_B_X1_Y1.gds \
  --output-lef flow/align_macro/CMC_S_NMOS_B_X1_Y1.lef
```

The source macro is preserved as `CMC_S_NMOS_B_X1_Y1.source.gds`.

The streamout step applies `flow/scripts/signoff/add_gnd_bridge.py` to the
mixed GDS. This is physical geometry, not a disconnected-pin waiver. The
bridge connects the top-level GND M2 pad to the macro GND escape through an
empty M2 corridor. The same post-streamout step reroutes the `ANA_DB` jog into
the macro DB landing, preserving that signal while satisfying the upstream
M2 spacing rule; both paths are checked by the same drawing DRC used for
signoff.

### Explicit connected-power core experiment

The ordinary routed GDS from a `RUN_PDN: false` run does not, by itself,
physically join every standard-cell VDD/GND landing.  The powered access
library and `flow/run_connected_power_route.sh` provide a reproducible
core-level experiment that routes both supplies as normal M1/M2 nets after a
completed LibreLane run.  Start from the official mixed-counter example in the
LibreLane development shell:

```bash
./flow/run_librelane_tr1um_access_power.sh \
  flow/designs/tr1um_mixed_counter/config_access.yaml \
  --run-tag mixed-power-nopdn-1

./flow/run_connected_power_route.sh \
  flow/designs/tr1um_mixed_counter/runs/mixed-power-nopdn-1 \
  /tmp/tr1um-connected-power
```

The second command deliberately runs as an isolated post-route derivation. It
does not replace or mutate any of the saved LibreLane stages. It writes a new
DEF, ODB, GDS, OpenROAD report, KLayout drawing-DRC report, raw conductive-graph
check, and netlist-only LVS extraction to the requested output directory.

Two routing-only LEFs make the supply topology unambiguous:

- `TR-1um_access_cells_signal_power.lef` exposes dedicated M2 power landings
  for the six cell types used by this reference design while treating their
  internal M1 shapes as obstructions. Other library cells retain their normal
  abstraction and require the same qualification before this method is
  generalized to designs that use them.
- `CMC_S_NMOS_B_X1_Y1.routing.lef` gives the macro's physically separate body
  ground escape the temporary terminal name `GNDP`; the routing Tcl explicitly
  connects `u_ana/GNDP` to `GND`.

The derived DEF keeps VDD and GND classified as `SIGNAL`. This is required so
OpenDB serializes the detailed-route `dbWire` geometry; changing them back to
special POWER/GROUND nets without converting the wires to `dbSWire` drops the
physical routes. Their supply meaning remains defined by the physical VDD/GND
labels and the Verilog/CDL contract.

For the reference run, the post-route result has zero OpenROAD detailed-route
violations, zero hard KLayout drawing-DRC items, one conductive component for
all 24 VDD/VCC labels, and one conductive component for all 28 GND/VSS labels.
The checker also fails if the two supply components are shorted or a power
label is not on M1/M2 metal.

This result is currently **core-level evidence, not a framed tapeout signoff**.
Directly joining the narrow core supply routes to the official frame pads
causes the foundry deck to classify the connected network as pad metal and
apply the M1P/M2P 14 um spacing and 40 um lead-out rules. That pad-transition
geometry remains to be designed and qualified. Layer 250 bridge metadata is
not required by this connected-core method and is not used as connectivity
evidence.

#### 24-character UART channel-power experiment

`tr1um_uarttx_big` is a 14.7456 MHz, 115200-baud transmitter in a
1000 by 1000 um macro.  It continuously emits
`SYMBIOTIC@YG@CKDUR@ROBIN@@@@@@@@`.  The design contains 103 synthesis
instances: 102 logic/sequential cells plus one physical TIELO.  Its fixed
placement uses seven site-aligned rows, with five empty row intervals reserved
for the channel buses.

Run the complete generic flow from the LibreLane development shell:

```bash
./flow/designs/run_digital_tests.sh \
  --tag uart-big-1000x1000-run tr1um_uarttx_big
```

The design-local `power_channels.json` supplies the row offsets and right-edge
trunk inset used by `run_digital_core_flow.sh`.  The generic connected-power
stage then performs OpenROAD detailed-route checking, KLayout drawing DRC,
explicit supply-continuity checks, extraction, and strict transistor-level
LVS.  The optional dedicated reroute entry point uses the same design and
channel configuration:

```bash
./flow/run_uart_connected_power.sh \
  flow/designs/tr1um_uarttx_big/runs/<tag>
```

Both paths are core-level experiments.  They do not qualify the MPW frame/pad
transition, IR drop, electromigration, or final tapeout reliability.

For any standalone digital core with a routed GDS, matching DEF, and powered
post-route Verilog, run the same strict comparison without the UART routing
stage:

```bash
./flow/run_core_lvs.sh \
  core.gds core.def core.pnl.v core_top /tmp/core-lvs
```

For a larger hardened hierarchy, put the `tr1um_uarttx_big` GDS/LEF in the
parent's macro views and instantiate its black-box Verilog.  Pass the strict
UART contract after the parent output directory; multiple macro contracts may
be listed:

```bash
./flow/run_core_lvs.sh \
  parent.gds parent.def parent.pnl.v parent_top /tmp/parent-lvs \
  uart-build/tr1um_uarttx_big.strict.cir
```

The builder checks the complete parent physical/Verilog instance population,
recursively includes the macro contract, stamps all parent DEF ports onto the
GDS label layers, and runs strict-port LVS.  In xschem, place
`tr1um_uarttx_big.sym`, connect `tx clk VDD VSS`, and include or concatenate
`tr1um_uarttx_big.strict.cir` with the parent SPICE netlist before running the
same KLayout LVS deck.  Do not use behavioral RTL as the LVS schematic: the
strict `.cir` file is the transistor-level physical contract.

The channel topology grows linearly with the number of cells, but it is not a
general power-grid generator.  A larger design should increase die area and
row count, retain routing channels, and re-run every check.  The 1.8 um M1 bus
width is the process drawing minimum used by this DRC experiment; tapeout use
also requires an IR-drop and electromigration assessment and may need wider or
parallel buses.  The common WN geometry requires foundry review before tapeout.

### Reproduction

Enter the LibreLane development shell, then run the access launcher above.
The resulting run must show `route__drc_errors: 0`,
`klayout__drc_error__count: 0`, and both disconnected-pin metrics at zero.

The final framed gate uses the repaired run's saved GDS and generated strict
contract:

```bash
RCX_DEF="$PWD/flow/designs/tr1um_mixed_counter/runs/gc-diode-repair13/final/def/tr1um_mixed_counter.def" \
bash flow/scripts/signoff/run_tr1um_signoff.sh \
  /tmp/tr_1um_mixed_counter_gc_diode_repair13.gds \
  tr_1um_mixed_counter \
  /tmp/gc-diode-repair13-strict-current.cir \
  /tmp/gc-diode-repair13-signoff-current
```

The strict contract is generated from the routed PNL Verilog, analog CDL,
independent frame extraction, and fixed standard-cell views from the
hierarchical cell extraction by
`flow/scripts/signoff/build_strict_mixed_contract.py`. It translates all core
instances from the PNL and never copies the routed top/core extraction
topology.

### Upstream PDK collateral sync (2026-09-16)

`libs.tech`, `Tools/`, and `Document/` were synced to `OpenSUSI/TR-1um`
`dev` @ `6afbd91` (the 2026-09-09 "Changes from DRC dry run 2 feedback" work):

| Merged from upstream | Local project content preserved |
|---|---|
| `tech/drc/run.drc`, `02_Device.drc`, `03_Electrical.drc` | `tech/def_layer_map.map` |
| `tech/drc/run_mdp.drc`, `IP62/00_Layers.drc`, `IP62/01_Basics.drc` | `lvs/01_Extract.lvs` top-level power contract |
| `tech/lvs/05_Compare.lvs` `equivalent_pins` | `lvs/04_Custom.lvs` device mapping |
| `libraries/TR-1um_frame_25x25.gds`, `TR-1um_STDCELL.gds` | `lvs/05_Compare.lvs` standard-cell flattening |
| `libraries/TR-1um_frame_25x25_GIO.gds` (new), xschem, `Tools/` | |

The numbers in the tables above were measured before this sync. After the
sync, on the same routed artifact and the same netlist:

| Gate | Before sync | After sync |
|---|---:|---:|
| Drawing DRC hard items | 0 | 22 |
| LVS | match | match |
| MDP | ok | ok |
| IP62 mask DRC hard items | 0 | 0 (22 `WAR06`) |

All 22 drawing items are `GC.ANT` floating-gate reports. They are the upstream
tightening of the chip-level substrate-connection check: pad-connected nets
are now exempt only through real pad recognition (`M2P`), so poly tied to the
analog macro ground must satisfy the new `GC_PAD` antenna path.

The repaired flow resolves those 22 reports with nine real `DIODE_N_X1`
antenna cells inserted on the four `clk`/`rst` input pairs and the analog
`ANA_G` input. `RUN_ANTENNA_REPAIR` remains disabled: this is deterministic
port protection, not a heuristic threshold-based insertion. The upstream
runsets were not weakened and no DRC waiver was added.

### Drawing DRC source/output parity

The checked-in drawing runset is gated against its source table by
`flow/scripts/signoff/check_drc_rule_parity.py` and
`flow/qualification/drc_rule_parity.json`:

```bash
python3 flow/scripts/signoff/check_drc_rule_parity.py \
  --manifest flow/qualification/drc_rule_parity.json
```

The checker compares exact source rule IDs with KLayout `.output()` category
prefixes. It never infers semantic aliases. A source rule missing from the
runset therefore requires an explicit disposition; rules without a disposition
or with `required`, `unknown`, or `not_implemented` are reported as TODOs.
`covered_by_alias`, `obsolete`, `advisory_only`, and `fab_accepted` are
reported as warnings. TODOs and warnings are nonblocking because the
manufacturer-supplied DRC collateral is known to be incomplete; malformed
manifests or unreadable inputs still fail closed. The top-level signoff wrapper
and the independent MPW flow run this gate before physical checks.

The current checked-in pair is intentionally `PASS_WITH_WARNINGS`: `GC.AN`,
`CC.S1`, `CS.S1`, `M1.W2`, `M1.PW`, and `M2.PW` are absent from the active
runset, and `GC.AN` still has unresolved `???` source values. The report keeps
all six visible for user review without stopping the physical flow.

The upstream DRC branch used for this checkout makes the Cat-4 rename
explicit: the 0.4 um spacing rules are `GA.AP` and `GA.AN`, while the
separate Cat-5 `GC.AN` row remains unresolved (`MIN`/`MAX` are `???`).
Regression collateral follows that distinction: `GA_AP` and `GA_AN` are
executable Cat-4 fixtures; no executable Cat-5 fixture is claimed until the
source threshold is published. `GC.ANT` remains the independent diode/floating
gate electrical rule.

### Current DRC regression

`TR-1um_DRC_Regression_TEST` is tracked as a top-level submodule. Its nested
`external/TR-1um` source submodule was removed; when used inside this project,
the harness resolves the parent checkout as `TR1UM_ROOT`. Run the current DRC
from the LibreLane nix-shell:

```bash
nix-shell "$HOME/Documents/librelane/shell.nix" --run \
  'cd "$HOME/Documents/TR-1um" && \
   python3 TR-1um_DRC_Regression_TEST/scripts/generate_all.py \
     TR-1um_DRC_Regression_TEST/unit_tests && \
   python3 TR-1um_DRC_Regression_TEST/scripts/batch_regression.py \
     TR-1um_DRC_Regression_TEST/unit_tests'
```

The regression result is evidence for user review, not a waiver: known
manufacturer-rule gaps are reported as TODOs/warnings, while actual hard
layout violations remain physical DRC failures.
The full run from this checkout produced the following current baseline after
aligning the executable Cat-4 spacing fixtures with the upstream `GA.*` rule
IDs and excluding the unresolved Cat-5 `GC.AN` fixture:

| Category | Total | Passed | Failed |
|---|---:|---:|---:|
| Cat-1 | 25 | 25 | 0 |
| Cat-2 | 67 | 67 | 0 |
| Cat-3 | 65 | 65 | 0 |
| Cat-4 | 46 | 24 | 22 |
| Cat-5 | 47 | 0 | 47 |
| Cat-6 | 50 | 27 | 23 |
| Cat-7 | 39 | 0 | 39 |
| Cat-8 | 60 | 30 | 30 |
| **Total** | **399** | **238** | **161** |

This is not a clean regression result. The 161 failures remain review items;
they are not converted into waivers by the parity manifest.

### LVS source/manual/runset parity

The active KLayout LVS contract is inventoried by
`flow/qualification/lvs_source_parity.json` and checked by
`flow/scripts/signoff/check_lvs_source_parity.py`. The manifest covers the
GUI wrapper, the active `tech/lvs/run.lvs` include order, both shared DRC
inputs, all five active LVS source files, the six tutorial files, and the
legacy `tech/lvs/IP62` tree that is explicitly excluded from the active
contract.

Run the source/manual/runset check directly with:

```bash
python3 flow/scripts/signoff/check_lvs_source_parity.py \
  --manifest flow/qualification/lvs_source_parity.json \
  --runset libs.tech/klayout/tech/lvs/run.lvs \
  --output /tmp/tr1um-lvs-source-parity.json
```

The current result is `PASS_WITH_WARNINGS`: seven active include directives
resolve to seven readable source files, and all local tutorial links now
resolve to files in the current tree. The manifest records four reviewed
semantic-drift claims (device extraction, passive extraction, custom-device
translation, and comparison behavior) plus one reference-only combiner
contract. These are evidence of documentation drift, not LVS waivers or proof
of source/manual semantic equivalence.

The full signoff wrapper and the independent MPW wrapper run this checker
before physical stages and write `lvs_source_parity.json` in their report
directory. Malformed manifests, missing active sources, include-order changes,
or invalid evidence references fail closed; reviewed tutorial drift remains a
visible non-blocking warning until the manual is refreshed.

The integrated wrapper smoke against the repaired framed inputs returned
`RC=0`; `/tmp/tr1um-lvs-parity-signoff/lvs_source_parity.json` recorded
`PASS_WITH_WARNINGS`, and its strict `lvs.log` emitted
`INFO : Congratulations! Netlists match.`.


## Final mixed-signal signoff evidence

The current signoff artifact is the repaired access-cell run
`flow/designs/tr1um_mixed_counter/runs/gc-diode-repair13`. It routes the
analog macro through its BEOL escape ring (M2 landing pads) and protects the
upstream GC-sensitive input nets with nine `DIODE_N_X1` cells.

| Metric | Result |
|---|---:|
| OpenROAD route DRC errors | 0 |
| KLayout drawing DRC errors | 0 |
| Standard-cell + macro instances | 22 (21 standard cells + 1 macro) |
| Antenna-cell instances | 9 |
| Setup WNS/TNS | 4980.94 / 0 |
| Hold WNS/TNS | 8.36454 / 0 |
| Unmapped cells | 0 |

OpenROAD reports zero antenna-violating nets and zero antenna violations.
The upstream KLayout report has `GC.ANT: ... = 0`, `WN.AN = 0`,
`V1.CO = 0`, `M2.S1 = 0`, and `"total": 0`.

The repaired framed GDS is
`/tmp/tr_1um_mixed_counter_gc_diode_repair13.gds`. It is framed
(2500 x 2500um, dbu 0.001, `OSS_FRAME` hierarchy) and was checked by the
complete local gate with a **strict, non-circular LVS contract**:

```text
MPW structural pre-check: PASS
Drawing DRC: 0 hard items
Strict LVS: INFO : Congratulations! Netlists match.
MDP: non-empty output
IP62 mask DRC: 0 hard items
RCX: 20-net DEF-derived engineering SPEF
```

The exact report bundle for this framed revision is tracked by
`flow/qualification/analog_signoff_manifest.json` under
`flow/qualification/reports/gc-diode-repair13/`:

| Evidence | Bundled path |
|---|---|
| Framed drawing DRC | `drc.lyrdb` |
| Contract-aware ERC | `erc.json` |
| Netlist-label/ERC input | `netlist_labels.json` |
| Strict LVS log/database | `lvs.log`, `lvs.lvsdb` |
| MDP output and post-MDP DRC | `tr_1um_mixed_counter_mdp.gds`, `ip62_drc.lyrdb` |
| DRC/LVS source parity | `drc_rule_parity.json`, `lvs_source_parity.json` |

All listed report files are exact byte copies of the `/tmp` signoff run and
are classified `engineering_only`; the regression mismatches and analog
qualification blockers remain open.


### RC/PEX estimate basis and limits

The open IP62 process manual is
`openIP62/IP62/Technology/doc/OS00_リファレンスマニュアル_rev1.1.pdf`.
Its document list explicitly marks parasitic extraction as unavailable and
does not provide a foundry metal RC/PEX deck. It does provide process context,
including the 5V/HV CMOS process description, nominal M1/M2 design-rule
widths, and current limits (M1 900uA at 2um; M2 3.7mA at 3um).

Accordingly, `flow/scripts/analysis/estimate_tr1um_rc.py` does not claim
foundry data. It reads the checked-in derived technology LEF and computes:

```text
R_edge = sheet_resistance * segment_length / route_width
C_edge = segment_length * (area_capacitance * route_width + 2 * edge_capacitance)
```
`route_width` is the explicit DEF route width; widthless routes use the
nominal LEF routing width. Each split graph edge receives its own R/C terms.

Current derived values:

| Layer | R | C |
|---|---:|---:|
| M1 | 0.027777778 ohm/um | 0.163000 fF/um |
| M2 | 0.010000000 ohm/um | 0.152500 fF/um |
| M3 (reserved) | 0.010000000 ohm/um | 0.160000 fF/um |
| V1 | 1.0 ohm nominal | 0.5--2.0 ohm sensitivity range |

The estimator applies +/-50% sensitivity bands to sheet resistance and
capacitance. `flow/signoff/run_estimated_rcx.sh` delegates network construction
to `flow/scripts/analysis/extract_tr1um_parasitics.py`. The extractor reads
explicit DEF route widths (using the nominal LEF width only for widthless
routes), resolves DEF/LEF pin connections, splits each routed segment at
endpoints, vias, and located terminals, and emits a distributed SPEF. It also
emits two sidecars beside the SPEF: `<base>.parasitics.json` (the source,
geometry, width, node, and resistor-edge ledger) and `<base>.pex.sp` (the
distributed RC network for an analog deck). DEF coordinate extension fields
are not vias.

The generated engineering network includes width-aware same-net wire
capacitance, distributed sheet-resistance edges, explicit V1 resistor edges,
parallel-segment lateral fringe coupling for M1--M1, M2--M2 (and M3--M3 when
routed), and adjacent-metal M1--M2 overlap coupling from DEF route bounding
boxes. M3 vertical overlap to M2 and optionally M1 is derived from GDS/DEF
geometry. The network also includes GR/F_RS capacitance to the classified PSUB
or NW net, active RR/F_RR PLUS-to-bulk capacitance from the checked-in
compact-model formula, and GC/MOS gate-to-AP/AN overlap terms from the BSIM3
`cgsl`/`cgdl` values. SPEF `*CONN` records carry DEF ports and placed-cell
pin directions/cell types; zero-ohm terminal attachments connect those
physical terminals to the nearest routed graph node.
Only device terms whose terminals resolve to the selected top-level routed
nets are materialized in SPEF/SPICE; nested KLayout devices remain in the
ledger with a bounded warning rather than being assigned to an unrelated net.
The coefficients and provenance are explicit in
`flow/scripts/analysis/tr1um_parasitic_model.json`; no value is presented as
foundry-qualified. `run_tr1um_signoff.sh` passes the KLayout extracted SPICE
view to RCX automatically. Set `RCX_INCLUDE_DEVICE_CAPS=0` when the analog
compact models already own the RR/GC terms and the generated network is used
only for wire coupling.

The extractor rejects unsupported routed layers and via types instead of
silently dropping them. This is useful for engineering sensitivity/timing
analysis, but remains **not foundry-qualified RC/PEX**. No RC estimate is
used as evidence that the MPW submission has qualified parasitic extraction.

### Reserved M3 and RC scope

The technology LEF defines an M3 routing layer, but the current digital router
is explicitly constrained to M1/M2 (`RT_MIN_LAYER: M1`, `RT_MAX_LAYER: M2`).
The estimator still reports M3's LEF-derived first-order values under
`reserved_layers`; the new extractor accepts explicit M3 DEF routes and
consumes selected-hierarchy M3 GDS geometry for vertical overlap. Unlabelled
M3 geometry is conservatively associated with the configured substrate net
(`VSS` by default), while labelled M3 geometry becomes an explicit coupling
aggressor. GDS overlap uses axis-aligned bounding boxes and is therefore an
engineering bound, not a calibrated field solve.

M3 remains reserved for the current router and no V2 route model is silently
invented. A future M3-enabled flow still requires foundry coupling data and
fresh RC correlation; the checked-in model is only a transparent sensitivity
proxy.

### Current engineering RCX assumption log

This is the update point for the non-foundry RCX assumptions. The executable
values live in `flow/scripts/analysis/tr1um_parasitic_model.json`; update that
file and this log together when a foundry deck, measured correlation, or
better process documentation becomes available.

- **Baseline interconnect RC:** M1, M2, and reserved M3 use the derived LEF
  values above. Each routed segment uses its explicit DEF width when present;
  widthless routes use the nominal LEF width. Split graph edges materialize
  `R = Rsheet * L / W` and `C = L * (Carea * W + 2 * Cedge)`. The stated
  +/-50% ranges are engineering sensitivity bands, not confidence intervals.
- **M1/M2 overlap coupling:** use `0.0000175 pF/um2` from
  `vertical_coupling.M2_M1` as an engineering proxy for adjacent-metal
  overlap. The extractor applies it to DEF M1/M2 route bounding-box
  intersections; no foundry inter-metal coupling coefficient is published.
- **Via resistance:** V1 is set to 1.0 ohm nominal with a 0.5--2.0 ohm
  sensitivity range because no via resistance is published.
- **Lateral fringe coupling:** M1, M2, and M3 use 0.00005 pF/um edge
  capacitance. The spacing attenuation lengths are 1.8 um for M1 and 3.0 um
  for M2/M3; the modeled maximum spacings are 5.4 um and 9.0 um respectively.
  This is an exponential-spacing proxy, not a calibrated coupling deck.
- **M3 vertical coupling:** M3--M2 uses 0.0000175 pF/um2; M3--M1 and
  M3--substrate use 0.000020 pF/um2. These are area-density proxies. GDS
  overlap is measured with axis-aligned bounding boxes rather than polygon
  clipping or a field solve.
- **GR/F_RS capacitance:** use 0.000615 pF/um2 (0.615 fF/um2), borrowed from
  the legacy CSIO coefficient because no direct GR coefficient is published.
  The total is `C = density * W * L` and is split equally over PLUS/MINUS.
  GR defaults to PSUB/VSS; overlap with WN classifies it as NW/VDD.
- **RR/F_RR capacitance:** evaluate the checked-in `F_RR c_d0` PLUS--SUB
  compact-model expression; `c_d1` MINUS--SUB is zero in that model. This is
  source-derived rather than a new coefficient, and the compact model owns
  the term.
- **GC/MOS overlap:** use BSIM3 `cgsl`/`cgdl`: 1.81 fF/um for PMOS and
  2.02 fF/um for NMOS. These are source-derived compact-model terms; do not
  add them a second time to an analog deck.
- **Geometry and hierarchy:** unlabelled M3 is assigned to the configured
  substrate net; labelled M3 is treated as an aggressor. Only device terms
  that resolve to selected top-level routed nets enter SPEF/SPICE. Nested
  KLayout devices stay ledger-only with a warning. No V2 route model or
  foundry-qualified substrate/inter-metal coefficient is assumed.

These assumptions are engineering placeholders, not release qualification.
New source data must replace the corresponding proxy and its provenance, then
be re-correlated before the remaining qualification TODO is closed.

Direct evidence from the repaired run and framed wrapper (`RC=0`):

| Gate | Result |
|---|---|
| MPW structural pre-check | PASS |
| Framed drawing DRC | 0 hard items |
| Framed LVS (strict contract) | Netlists match |
| MDP | generated |
| IP62 mask DRC | 0 hard items |
| RCX | DEF-derived SPEF, 20 nets (engineering estimate, not foundry-qualified) |

The contract generator is
`flow/scripts/signoff/build_strict_mixed_contract.py`; it never copies the
routed layout's topology (the earlier `build_mixed_extracted_contract.py`
extraction-echo contract is deprecated and kept only for debugging). The
RCX recipe `flow/signoff/run_estimated_rcx.sh` derives a distributed
SPEF/RC network from routed DEF geometry, adds optional GDS vertical-overlap
and extracted-device terms, and writes distributed RC/SPICE and ledger
sidecars; the status remains an explicit engineering estimate because no
foundry RC/PEX deck exists for TR-1um.

The macro GND issue is fixed by a reproducible post-streamout bridge in
`flow/scripts/signoff/add_gnd_bridge.py`, integrated into the overridden
`KLayout.StreamOut` step. The bridge connects the top-level GND M2 pad to the
macro GND escape through an empty, DRC-checked M2 corridor. The script also
reroutes the `ANA_DB` macro signal around the forbidden M2 jog instead of
shorting it into the GND bridge. These are physical routes, not
disconnected-pin waivers, and the strict LVS contract preserves both logical
nets.

Current mixed-run evidence:

```text
design__disconnected_pin__count = 0
design__critical_disconnected_pin__count = 0
route__drc_errors = 0
route__antenna_violation__count = 0
klayout__drc_error__count = 0
```

The saved repaired routed GDS contains the GND bridge and the corrected
`ANA_DB` detour; direct drawing DRC is 0. The framed wrapper returns `RC=0`,
strict LVS matches, IP62 mask DRC has 0 hard items, and the RCX estimate is
generated.

The no-PDN configuration remains intentional: OpenROAD PDN generation cannot
consume this analog macro because it has no full power-grid shape/via set.
The explicit bridge supplies the missing physical GND connection, but it is
not an IR-drop, electromigration, or power-grid signoff result.

### Why OpenROAD PDN is not enabled for this macro

The current analog leaf is an NMOS-only, ground-referenced macro:

```text
.SUBCKT CMC_S_NMOS_B_X1_Y1 G DA SA DB SB GND
M1 DA G SA GND NMOS ...
M2 DB G SB GND NMOS ...
```

It has no real `VDD` pin and therefore cannot honestly use the normal
LibreLane hook:

```yaml
PDN_MACRO_CONNECTIONS:
  - "u_ana VDD GND VDD GND"
```

OpenROAD's standard macro PDN grid also requires a macro grid with usable
PG geometry. The current escape-ring macro has legal M1/M2 landing pads, but
does not provide the internal grid topology expected by `define_pdn_grid -macro`.
The macro-grid experiment (`runs/pdn-experiment`) failed with
`PDN-0232`/`PDN-0233`. A second ground-only experiment with macro-grid
connection disabled generated the standard-cell grid but failed the GND
connectivity check (`PSM-0069`) at the macro landings and then failed detailed
placement (`DPL-0033`).
The checked-in PDN recipe now honors `PDN_CONNECT_MACROS_TO_GRID`: when it is
false, no macro grid is emitted. This prevents an accidental macro-grid
attempt, but it does not make the macro power contract valid. The canonical
configuration also sets `ERROR_ON_PDN_VIOLATIONS: true`, so a future
`RUN_PDN: true` experiment fails rather than yielding a signoff artifact with
deferred PSM violations.

Those experiments were intentionally removed from the canonical configuration.
The conservative current solution is M1/M2-only: keep standard PDN generation
disabled, route the named GND connection with the explicit post-DRT route, and
apply the same physical GND bridge during KLayout streamout. The
disconnected-pin checker remains strict. Enabling true macro PDN requires a
ground-only PDN hook that excludes the macro from broad standard-cell global
connections, plus an internal macro PG grid/landing contract; adding a fake VDD
pin is not acceptable. M3 is not used or planned because it is unavailable for
fabrication in this process.

### Digital-design PDN comparison

The same review was applied to the other digital designs rather than
assuming that the analog leaf's ground-only classification generalized to
them. The generated report inventories 11 `config_access.yaml` files:
`tr1um_alu8`, `tr1um_busdecode`, `tr1um_crc8`, `tr1um_fifo4`,
`tr1um_fsm_lock`, `tr1um_irqctrl`, `tr1um_popcount8`, `tr1um_pwm4`,
`tr1um_regfile4x4`, `tr1um_spitx`, and `tr1um_uarttx_big`. Every one keeps
`RUN_PDN: false` and substitutes `OpenROAD.IRDropReport`; completed standard
flow runs therefore do not constitute PDN/IR evidence.

Two representative powered experiments were exercised:

- Forcing PDN and IRDropReport on `tr1um_alu8` generated the grid but reported
  `PSM-0025` at grid generation and `PSM-0038`/`PSM-0039` followed by
  `PSM-0069` during IR analysis. The probe explicitly set
  `PDN_ENABLE_GLOBAL_CONNECTIONS`, `SCL_POWER_PINS: [VDD]`, and
  `SCL_GROUND_PINS: [GND]`; the GeneratePDN log still reports zero global
  connections and no accepted numeric IR result. It also warns that
  `VSRC_LOC_FILES` is absent.
- The UART `connected_power` experiment creates explicit VDD/GND special-net
  routes and is useful as a routing artifact, but a direct VDD PDNSim probe
  reports `PSM-0038`, `PSM-0039`, and `PSM-0069`. It is not EM/IR signoff.

The durable evidence is
`flow/qualification/reports/pdn-emir/pdn_emir.json` and
`flow/qualification/reports/pdn-emir/uart_connected_power_pdn_probe.txt`.


## Regression and MPW-template integration

The project consumes the neighboring repositories as external authoritative
inputs rather than copying their large fixture trees into this repository:

### `../TR-1um_DRC_Regression_TEST`

The regression repository is the source of the foundry-rule fixture taxonomy
(`Cat-2` through `Cat-8`, including M1/M2/V1, active/poly, contact, gate,
well, and enclosure/spacing cases). The local flow keeps the same PDK DRC
runsets under `libs.tech/klayout/tech/drc/` and uses them in two ways:

1. per-cell/access-library qualification through
   `flow/scripts/access/qualify_ip62_beol_cells.py`; and
2. full-design drawing DRC through `KLayout.DRC` plus the XML report checker
   `flow/scripts/signoff/check_klayout_report.py`.

The regression fixtures are intentionally not duplicated under `flow/`; use
the sibling checkout when running the complete fixture taxonomy. The local
project artifact is the PDK-rule execution path and the qualification scripts,
which prevents fixture copies from drifting from the authoritative regression
repository.

### `../TR-1um_MPW_template` (git submodule)
The MPW template is pinned as a repository-root git submodule. From a fresh
checkout, initialize it with:

```bash
git submodule update --init --recursive
```

The signoff scripts default to this checkout-local copy. Set `MPW_TEMPLATE`
only when deliberately checking another template revision.

The MPW template defines the submission contract and CI gate sequence:

- exactly one top cell;
- `tr_1um_` top-cell naming;
- dbu `0.001um`;
- exact `2500 x 2500um` frame extent;
- `OSS_FRAME`/`OSS_FRAME_TEG` hierarchy;
- drawing DRC;
- strict LVS;
- MDP generation;
- IP62 mask-layer DRC.

This repository integrates that contract in:

- `flow/scripts/signoff/mpw_precheck_klayout.py` — KLayout-runtime adapter
  for the template pre-check;
- `flow/scripts/signoff/run_tr1um_signoff.sh` — local pre-check, drawing DRC,
  LVS, MDP, IP62 DRC, and RCX sequence;
- `flow/scripts/signoff/check_klayout_report.py` — hard-item versus WAR-item
  report policy.

The local wrapper intentionally adds two project-specific safeguards: it
requires a positive LVS match marker, and it derives a real DEF/GDS-based
engineering SPEF plus an auditable parasitic ledger while explicitly retaining
the not-foundry-qualified status.
The wrapper does not replace the MPW template's required geometry or DRC/LVS
gates.
The local wrapper defaults to the pinned submodule and does not depend on an
unrelated sibling checkout.

Reproduce the full local gate from the repaired access run with:

```bash
cd "$HOME/Documents/librelane"
nix-shell
cd "$HOME/Documents/TR-1um"
RCX_DEF="$PWD/flow/designs/tr1um_mixed_counter/runs/gc-diode-repair13/final/def/tr1um_mixed_counter.def" \
bash flow/scripts/signoff/run_tr1um_signoff.sh \
  /tmp/tr_1um_mixed_counter_gc_diode_repair13.gds \
  tr_1um_mixed_counter \
  /tmp/gc-diode-repair13-strict-current.cir \
  /tmp/gc-diode-repair13-signoff-current
```

The verified result is `RC=0`, with zero hard drawing DRC items, strict LVS
match, generated MDP, zero hard IP62 mask DRC items, and a DEF-derived
20-net engineering SPEF.

## IP62 digital-flow validation

The representative design is `flow/designs/tr1um_counter`, which exercises
`DFFR`, `BUF_X1`, `INV_X1`-class logic, NAND/NOR/XOR/AND cells, reset logic,
placement, routing, STA, streamout, and KLayout DRC.

The native route-repair run is
`flow/designs/tr1um_counter/runs/native-manual-drt64b`.
It reports 0 OpenROAD detailed-route DRC errors, 93 KLayout drawing-layer DRC
errors, and zero setup/hold WNS/TNS.

The canonical access route-repair run is
`flow/designs/tr1um_counter/runs/access-canonical-final`.
It reports 0 OpenROAD detailed-route DRC errors, 0 KLayout drawing-layer DRC
errors, and zero setup/hold WNS/TNS. The repair moves five source-preserving
M2 access landings (`NAND2/Y`, `NAND3/B`, `NAND3/Y`, `XNOR2/Y`, `XOR2/Y`) away
from row-edge spacing interactions. The legal landing coordinates are encoded
in `flow/scripts/access/gen_ip62_beol_access_strict.py` and the generated access
library is qualified by `flow/scripts/access/qualify_ip62_beol_cells.py`.

Access-cell qualification is independent and complete: all 38 derived cells
pass the original per-cell qualification before the experimental power-bridge
variants. The canonical signal-only access run is the verified digital baseline;
its generated library is restored under
`flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell_access/`.

### Generated access-library views and LEF obstructions

`flow/scripts/access/gen_ip62_beol_access_strict.py` regenerates the derived
access library from the immutable GDS cells under `STDLIB/LogicCells/gds`.
Its outputs include the per-cell `flow_gds/*.gds` and `lef/*.lef` views, the
aggregate `gds/TR-1um_stdcell_access.gds` and
`lef/TR-1um_access_cells.lef` views, and `access_manifest.json`. The aggregate
LEF concatenates the individual cell abstracts, so one generator change can
appear twice and produce a large textual diff without adding new cells.

The generated LEFs intentionally contain conservative `OBS` rectangles on
`V1`. OpenROAD sees the routing abstract but not the complete transistor-level
FEOL geometry in the source GDS. Without these obstructions it can create an
M1-to-M2 via that is legal in the abstract but violates the foundry spacing
rules after streamout. The generator therefore obstructs existing V1 geometry
and the following rule-expanded FEOL regions, clipped to the cell boundary:

- gate layers `GC` and `GR`, expanded by 1.2 um; and
- contact layer `CO`, expanded by 1.0 um.

These LEF rectangles are router restrictions only. They are not new physical
GDS wires, vias, pins, devices, or logical cells. Polygon decomposition can
emit many rectangles for a single obstruction region, particularly in the
aggregate LEF.

KLayout rewrites GDS library and structure creation/modification timestamps
when these views are regenerated. Consequently, Git can report binary GDS
changes even when every non-timestamp GDS record, including all geometry, is
identical. Review generated GDS changes semantically rather than treating a
byte-level timestamp difference as a layout change. The generated manifest
also records absolute source and output paths, so regenerating it on another
machine can produce path-only changes.

The current FEOL obstruction collector examines shapes directly owned by each
top cell; it does not recursively collect FEOL shapes from instantiated child
cells. Hierarchical source cells therefore require explicit checking before
assuming that the generated V1 obstruction covers child geometry. Per-cell
qualification and final official IP62 DRC remain mandatory; the LEF
obstruction is a routing guard, not a signoff waiver.

The canonical signal-only access baseline intentionally omits PDN. The final
powered access experiment is `flow/designs/tr1um_counter/runs/power-access-cleanup-final`.
It preserves the verified access placement, reports zero detailed-route DRC,
zero KLayout drawing DRC, zero disconnected pins, and zero setup/hold timing
violations.

The remaining LibreLane warnings are classified as follows:

- **Global-route congestion:** accepted for this sparse 1um experiment. The
  global router reports a small coarse-grid overflow, while detailed routing
  and final KLayout DRC are clean. Revisit only if routing margin or scalability
  becomes a design requirement.
- **Wire-length threshold:** no project requirement or validated threshold is
  defined. LibreLane therefore skips this policy checker. Total and maximum
  routed wire lengths remain reported in `metrics.json`; no arbitrary limit is
  being invented to silence the warning.
- **IR drop / EM:** no public foundry V1 resistance or qualified
  power-current model is available. The checked-in report at
  `flow/qualification/reports/pdn-emir/pdn_emir.json` therefore records
  engineering evidence only: the post-streamout M2 GND bridge is 891.2 um
  long and 3.0 um wide, giving 8.912 ohm nominal under the repository RC
  estimate and a 4.456..13.368 ohm sensitivity band. The canonical DEF has
  no GND route because the bridge is GDS-only. A first-order DC estimate uses
  `R = R_sheet * L / W` per metal segment, adds via/contact resistances when
  known, solves the PDN resistor network, and reports `V_drop = I * R`. This
  is a sensitivity model, not tapeout signoff.
- **Magic DRC:** intentionally disabled. KLayout is the active TR-1um drawing
  and IP62 mask rule engine; the checked-in Magic technology is diagnostic-only
  and is not claimed as an independent signoff deck.

OpenROAD's PDNSim documentation defines static IR analysis in terms of a
placed/PDN-synthesized grid, voltage sources, net voltage, instance power, and
source-model selection; see
https://openroad.readthedocs.io/en/latest/main/src/psm/README.html.
The sheet-resistance/Ohm's-law first-order model is also described in Texas
Instruments' PDN application note:
https://www.ti.com/lit/an/sprace6/sprace6.pdf.

Strict top-level LVS passes for the framed canonical GDS with the generated
physical-contract schematic at `flow/signoff/tr1um_counter.cir`. The contract
is generated from the powered routed netlist and an authoritative extraction
of the immutable framed physical hierarchy. It therefore preserves the
layout's exact VDD/VSS and standard-cell pin ordering without accepting a
port mismatch or flattening away cell connectivity.
Regenerate the contract after changing the framed GDS or powered routed netlist:

```bash
rm -rf /tmp/tr1um-strict-lvs-contract
mkdir -p /tmp/tr1um-strict-lvs-contract
klayout -b -zz -r libs.tech/klayout/tech/lvs/run.lvs \
  -rd input="$PWD/flow/signoff/tr_1um_counter_access_canonical.gds" \
  -rd top_cell=tr_1um_counter -rd netlist_only=true \
  -rd extracted=/tmp/tr1um-strict-lvs-contract/physical.extracted \
  -rd report=/tmp/tr1um-strict-lvs-contract/extraction.lvsdb
python3 flow/scripts/signoff/build_strict_lvs_contract.py \
  --physical-extracted /tmp/tr1um-strict-lvs-contract/physical.extracted \
  --powered-netlist flow/designs/tr1um_counter/runs/access-canonical-final/final/pnl/tr1um_counter.pnl.v \
  --output flow/signoff/tr1um_counter.cir
```


The regenerated canonical access frame is
`flow/signoff/tr_1um_counter_access_canonical.gds`.

### Reproduce the tapeout gates

From the repository root, start the local LibreLane development shell before
running any flow or signoff command:

```bash
cd "$HOME/Documents/librelane"
nix-shell
cd "$HOME/Documents/TR-1um"
```

Run the following commands from inside that `nix-shell` session.


## Analog macro signoff evidence

The final composite analog macro is:

```text
flow/align_macro/CMC_S_NMOS_B_X1_Y1.gds
flow/align_macro/CMC_S_NMOS_B_X1_Y1.lef
flow/align_macro/CMC_S_NMOS_B_X1_Y1.cdl
flow/align_macro/CMC_S_NMOS_B_X1_Y1.bb.v
```

The reproducible macro gate is:

```bash
bash flow/scripts/align/run_align_macro_signoff.sh \
  flow/align_macro/CMC_S_NMOS_B_X1_Y1.gds \
  CMC_S_NMOS_B_X1_Y1 \
  flow/align_macro/CMC_S_NMOS_B_X1_Y1.cdl \
  /tmp/tr1um-cmc-macro-signoff-final \
  flow/align_macro/CMC_S_NMOS_B_X1_Y1.lef
```

Verified output:

| Gate | Result |
|---|---|
| Drawing DRC | 0 hard items |
| Strict LVS | `INFO : Congratulations! Netlists match.` |
| MDP generation | non-empty output |
| IP62 mask DRC | 0 errors; 6 warnings |

The warnings are informational categories from the mask-layer runset. Magic
remains diagnostic-only and is not used as the authoritative TR-1um gate.

The macro is integrated into the current routed mixed-signal counter through
the `MACROS` contract in `flow/designs/tr1um_mixed_counter/config_access.yaml`.
The access flow uses the qualified BEOL escape-ring macro, disables unsafe
access-cell mirroring, routes the macro signals, and applies the reproducible
post-streamout GND bridge. Current mixed-flow evidence is documented in
`## Final mixed-signal signoff evidence` above.
The canonical frame can be regenerated from the verified access run with:

```bash
python3 flow/scripts/signoff/assemble_canonical_access_frame.py
```

This consumes the `access-canonical-final` streamout and writes:

```text
flow/signoff/tr_1um_counter_access_canonical.gds
```

Run the pre-LVS MPW gates independently:

```bash
rm -rf /tmp/tr1um-mpw-reproduction
TR1UM_FRAMED_GDS="$PWD/flow/signoff/tr_1um_counter_access_canonical.gds" \
TR1UM_FRAMED_TOP=tr_1um_counter \
TR1UM_MPW_REPORT=/tmp/tr1um-mpw-reproduction \
python3 flow/scripts/signoff/run_mpw_checks_independent.py
```

Expected result:

```text
MPW structural pre-check: PASS
LVS source/manual/runset parity: PASS_WITH_WARNINGS (reviewed drift warnings)
Drawing DRC: 0 report items
IP62 mask DRC: 0 report items
MDP: non-empty GDS
```

The strict tapeout wrapper then runs the same pre-check, drawing DRC, LVS,
MDP, mask DRC, and qualified RC/PEX gate in order:

```bash
rm -rf /tmp/tr1um-tapeout-reproduction
flow/scripts/signoff/run_tr1um_signoff.sh \
  "$PWD/flow/signoff/tr_1um_counter_access_canonical.gds" \
  tr_1um_counter \
  "$PWD/flow/signoff/tr1um_counter.cir" \
  /tmp/tr1um-tapeout-reproduction
```

The strict LVS stage reports:

```text
Starting TR-1um LVS Comparison in strict port mode
flag_missing_ports enabled: missing/mislabeled top-level ports are treated as errors
INFO : Congratulations! Netlists match.
```

`RCX_COMMAND` is optional. When unset, the wrapper uses the repository's
accepted deterministic TR-1um RCX recipe; set it explicitly to use a different
qualified extractor. For the mixed-signal framed top, `RCX_DEF` is mandatory
and must point to the exact routed DEF revision that produced the submitted
GDS; a same-name DEF from another run is not sufficient.

For an extraction-only diagnostic, which is not a signoff pass, use:

```bash
rm -rf /tmp/tr1um-lvs-extraction-only
LVS_NETLIST_ONLY=1 flow/scripts/signoff/run_tr1um_signoff.sh \
  "$PWD/flow/signoff/tr_1um_counter_access_canonical.gds" \
  tr_1um_counter \
  "$PWD/flow/signoff/tr1um_counter.cir" \
  /tmp/tr1um-lvs-extraction-only
```

This mode may complete extraction and continue to mask DRC, but it must not be
reported as top-level LVS closure. The known `WAR06: Floating SG Detected`
entries are warnings; the independent MPW checker records zero hard IP62 DRC
items for the canonical frame.

Verified current audit (assembled by `flow/scripts/signoff/assemble_canonical_access_frame.py`,
checked by `flow/scripts/signoff/run_mpw_checks_independent.py`, and compared with
`flow/signoff/tr1um_counter.cir`):
| Gate | Runset or artifact | Current result |
|---|---|---|
| MPW structural precheck | `flow/scripts/signoff/mpw_precheck_klayout.py` | PASS |
| Drawing DRC | `libs.tech/klayout/tech/drc/run.drc` | 0 hard items |
| IP62 mask DRC | `libs.tech/klayout/tech/drc/run_IP62.drc` | 0 hard items; 20 `WAR06` informational items |
| MDP | `libs.tech/klayout/tech/drc/run_mdp.drc` | non-empty mask GDS |
| Strict top-level LVS | `flow/signoff/tr1um_counter.cir` | PASS; `INFO : Congratulations! Netlists match.` |
| Digital flow gate | `flow/scripts/signoff/check_digital_tapeout_gate.py` | PASS |

The report gate treats categories beginning with `WAR` as informational and
fails on every other unvisited report item. This matches the runset's
`WAR06: Floating SG Detected` classification without waiving drawing or mask
DRC errors.

The full wrapper reaches the RC/PEX stage without an environment override.
`flow/signoff/run_estimated_rcx.sh` produces the repository's deterministic
DEF/GDS-derived distributed SPEF, distributed RC/SPICE network, and
ledger. A real foundry RC/PEX deck is unavailable; this estimate is explicitly
not foundry-qualified. `RCX_COMMAND` remains an optional override for a
separately qualified extractor.
The macro GND problem is fixed by the physical GND bridge integrated into
KLayout streamout. It is not a checker-classification waiver: the bridge is
present in the saved GDS, drawing DRC remains zero, and strict LVS still
matches. The current routed ODB/flow checker reports
`Found 0 disconnected pin(s), of which 0 are critical.`

The wrapper completed with the accepted RCX value and therefore does not claim
foundry correlation beyond this repository's declared TR-1um signoff policy.

No DRC rule was weakened and no timing violation was waived.

## Generic digital-core flow

`flow/run_tr1um_digital.sh` is the generic one-command entry point for an
access-library digital core. Run it from the LibreLane nix shell:

```bash
./flow/run_tr1um_digital.sh \
  flow/designs/tr1um_busdecode/config_access.yaml \
  tr1um_busdecode generic-1
```

It runs RTL lint/synthesis, deterministic sparse placement, signal routing,
ordinary M1 VDD/GND channel buses, OpenROAD detailed-route checking, KLayout
drawing DRC, physical supply-continuity checks, extraction, and strict LVS.

The final reusable outputs are under `runs/<tag>/connected_power/`: the
`*.connected_power.gds`, `*.macro.lef`, and `*.strict.cir` files.

### Five-design regression and reusable macro bundles

`flow/designs/run_digital_tests.sh` runs the complete test for the five
checked-in digital examples by default. From the LibreLane development shell:

```bash
./flow/designs/run_digital_tests.sh --clean-all --tag local-regression
```

Each design is simulated with Icarus Verilog, then run through LibreLane,
connected-power routing, OpenROAD and KLayout DRC, explicit supply-continuity
checks, strict transistor-level LVS, and hierarchy-view packaging. Every
stage name and executed command is included in
`flow/designs/artifacts/<tag>/logs/`. `--clean-all` removes all old `runs/`
contents only for the selected designs; without it, only the selected tag is
replaced.

A design name, design directory, or config YAML may be supplied, so no shared
script change is needed for another core:

```bash
./flow/designs/run_digital_tests.sh --tag my-core tr1um_uarttx_big
./flow/designs/run_digital_tests.sh --tag my-core /absolute/path/config_access.yaml
./flow/designs/run_digital_tests.sh --artifacts /tmp/macro-results \
  --tag my-core /absolute/path/to/design-directory
```

The config must contain `DESIGN_NAME`, and the design's `src/Makefile` must
provide `clean` and `sim` targets. A successful bundle contains:

| View | Hierarchical use |
|---|---|
| `<top>.gds` | connected-power physical macro placed in the parent GDS |
| `<top>.lef` | routing and pin abstract supplied to parent place-and-route |
| `<top>.blackbox.v` | interface supplied to parent synthesis |
| `<top>.pnl.v` | powered mapped implementation retained for inspection |
| `<top>.strict.cir` | transistor-level child contract used by parent LVS |
| `<top>.sym` | xschem subcircuit symbol |
| `SHA256SUMS` | integrity manifest for every packaged view |

For an xschem parent, place `<top>.sym` and add
`.include <top>.strict.cir` to the generated SPICE deck. For a hardened parent,
include the GDS/LEF and black-box views during implementation, then append one
or more child contracts to the strict parent LVS command:

```bash
./flow/run_core_lvs.sh parent.gds parent.def parent.pnl.v parent \
  parent_lvs child1.strict.cir child2.strict.cir
```

The packager fails if the GDS-extracted contract, LEF pins, and powered
Verilog interface differ. GDS `GND` is normalized to the LVS name `VSS`.

Adding another design does not require editing the standard-cell library or
shared flow scripts. Its directory supplies RTL, constraints, pin order,
`config_access.yaml`, and (when needed) `manual_place_access.tcl`. Keep every
other 75.6 um physical row empty. The current regressions show that 40 um
horizontal cell gaps work through 216 cells, while the shift-register-heavy
SPI block needs an 80 um gap. These are explicit design-local routability
parameters, not DRC waivers.

Five independent regression designs now pass RTL simulation, connected-power
GDS generation, zero-hard-item KLayout DRC, complete extracted VDD/VSS
connectivity, and strict LVS:

| Design | Function | Mapped instances | Verified run |
|---|---|---:|---|
| `tr1um_alu8` | registered 8-bit ALU | 216 | `clean-regression-2` |
| `tr1um_fifo4` | four-entry 4-bit FIFO | 95 | `clean-regression-2` |
| `tr1um_irqctrl` | four-source interrupt controller | 26 | `clean-regression-2` |
| `tr1um_spitx` | 8-bit SPI transmitter | 72 | `clean-regression-2` |
| `tr1um_busdecode` | registered 3-to-8 bus decoder | 18 | `clean-regression-2` |

The current experimental technology has only M1/M2 available for signal
routing. Placement locality and whitespace therefore matter much more than
nominal utilization; a small but poorly grouped register bank can be harder to
route than the 216-cell ALU. Scale by preserving empty rows, increasing local
horizontal gaps, and grouping strongly connected state before enlarging the
die. The signoff runner fails closed on any OpenROAD DRC, KLayout DRC, missing
supply connection, extraction mismatch, or strict-LVS mismatch.

### SPEF-backed post-layout digital simulation

Completed digital runs with a final PNL and engineering SPEF can be simulated
through the checked-in manifest
`flow/qualification/post_layout_digital_manifest.json`. The launcher uses a
distributed source SPEF directly when it contains `*CONN` and graph-node
records, runs OpenSTA to generate a fresh SDF, builds timing-capable Icarus
cell models, and annotates the PNL testbench:

```bash
cd "$HOME/Documents/librelane"
nix-shell
cd "$HOME/Documents/TR-1um"
./flow/designs/run_post_layout_tests.sh \
  --output /tmp/tr1um-post-layout
```

The default `--mode both` runs two views for each case. `strict` keeps the
source testbench clock and exposes timing failures. `slow` keeps the
SPEF-derived cell delays unchanged but slows the testbench clock so the
functional checks run after annotated delays settle. The command also runs the
design-local RTL testbench for comparison; `summary.json` contains the RTL,
strict, and slow status for every case. `--fail-on-strict` turns a strict
timing failure into a nonzero exit status.

The current manifest covers the six completed layout-backed cases
`tr1um_alu8`, `tr1um_fifo4`, `tr1um_irqctrl`, `tr1um_spitx`,
`tr1um_busdecode`, and `tr1um_uarttx_big`. Designs without both a final PNL
and a testbench are intentionally excluded.

The checked-in RC extractor emits distributed engineering SPEF files with
`*CONN` records, width-aware split graph nodes, distributed wire/via
resistors, node-ground capacitance, and explicit coupling records. The runner
passes such a source through to OpenSTA unchanged
(`spef_source_mode=distributed_direct`, with zero coupling collapse). For
legacy SPEFs with empty `*CONN`, it uses a deterministic fallback that
recovers PNL instance/pin connectivity, collapses coupling into each source
net's total capacitance, and replaces each scalar net resistance with a star
network (`spef_source_mode=legacy_lumped_bridge`). The result JSON records the
source mode and record counts. OpenSTA consumes the normalized source, but
Icarus cannot reliably annotate the generated top-level `INTERCONNECT` records
for these PNLs; the `*.for_iverilog.sdf` view removes those records while
retaining SPEF-derived cell `IOPATH` delays. The result JSON records the
removed and retained counts explicitly.

The final run produced the following delay-to-frequency conversion. For a
maximum cell delay \(t_{\mathrm{ns}}\), the reciprocal-delay rate is
\(f_{\mathrm{MHz}} = 1000 / t_{\mathrm{ns}}\), or
\(f_{\mathrm{Hz}} = 10^9 / t_{\mathrm{ns}}\). This is a delay-equivalent
rate, not a validated maximum operating clock frequency.

| Design | Max cell IOPATH delay (ns) | Reciprocal delay (MHz) | RTL | Strict | Slow |
| --- | ---: | ---: | :---: | :---: | :---: |
| `tr1um_alu8` | 8.365 | 119.546 | PASS | FAIL | PASS |
| `tr1um_fifo4` | 12.349 | 80.978 | PASS | FAIL | PASS |
| `tr1um_irqctrl` | 8.918 | 112.133 | PASS | FAIL | PASS |
| `tr1um_spitx` | 9.948 | 100.523 | PASS | FAIL | PASS |
| `tr1um_busdecode` | 10.309 | 97.003 | PASS | FAIL | PASS |
| `tr1um_uarttx_big` | 12.504 | 79.974 | PASS | PASS | PASS |

The audited Liberty inputs come from
`flow/char/char_liberty.py`: cell area is LEF `SIZE` width times height,
all 70 standard-cell input pins have rising/falling effective input-charge
measurements from ngspice, and combinational/DFF delay and output-transition
tables are SPICE-derived. DFF setup uses a 5% clock-to-Q push-out criterion
over the 0.5/1.0/2.0 ns slew grid. No hold arcs are emitted because the
extracted DFFR cell showed no positive hold push-out at the search
resolution. DFFS input charge is physical, but its CK-to-Q timing remains on
the DFFR electrical path until the extracted SET polarity is reconciled with
the Verilog contract.

The reciprocal rates above use the largest annotated cell `IOPATH` delay in
each generated SDF. They must not be used as signoff clock targets without
full timing analysis, clock uncertainty, setup/hold checks, and qualified
parasitics.

### OpenSTA path-class frequency estimates

The runner also emits one machine-readable OpenSTA max-path report per path
class under each case's `path_reports/` directory. The four classes are
`input -> output` (pure combinational), `reg -> reg`, `input -> reg`, and
`reg -> output`. The table reports the reciprocal of each class's largest
OpenSTA data arrival; the corresponding maximum delay is shown in
parentheses:

| Design | Input -> output (combinational) | Reg -> reg | Input -> reg | Reg -> output |
| --- | ---: | ---: | ---: | ---: |
| `tr1um_alu8` | n/a | n/a | 21.400 MHz (46.730 ns) | 119.531 MHz (8.366 ns) |
| `tr1um_fifo4` | n/a | 37.608 MHz (26.590 ns) | 62.500 MHz (16.000 ns) | 42.230 MHz (23.680 ns) |
| `tr1um_irqctrl` | 100.990 MHz (9.902 ns) | 56.370 MHz (17.740 ns) | 92.081 MHz (10.860 ns) | 63.532 MHz (15.740 ns) |
| `tr1um_spitx` | n/a | 36.778 MHz (27.190 ns) | 67.797 MHz (14.750 ns) | 58.207 MHz (17.180 ns) |
| `tr1um_busdecode` | n/a | n/a | 500.000 MHz (2.000 ns) | 64.309 MHz (15.550 ns) |
| `tr1um_uarttx_big` | n/a | 33.422 MHz (29.920 ns) | n/a | 31.279 MHz (31.970 ns) |

The frequency calculation is `f_MHz = 1000 / t_ns`. The reported path delay
is the endpoint data arrival measured from the OpenSTA launch edge: input
paths include the active input-delay constraint, and register paths include
source clock-to-Q. `max_logic_segment_delay_ns` in each result JSON records
the arrival difference from the path startpoint for separating the internal
logic segment. `n/a` means OpenSTA found no path in that class; it is not a
zero-delay or infinite-frequency result.

Only `reg -> reg` is a synchronous-clock candidate. These are reciprocal
path-rate estimates, not signoff Fmax values: the engineering timing library
now includes measured setup push-out constraints but does not include hold
arcs, complete clock modeling, or qualified parasitics. This calculation does
not add setup, hold, skew, or uncertainty margins. The `input -> reg`,
`reg -> output`, and combinational rates are interface or throughput
indicators rather than independent clock limits.

Native top-level KLayout DRC is intentionally removed from the tapeout scope;
the native branch remains a reference diagnostic only.

## General analog signoff guard framework

The repository now carries a reusable, fail-closed analog signoff contract in
`flow/qualification/analog_signoff_manifest.json`. It is intentionally scoped
to general analog and mixed-signal designs rather than claiming that the
current counter is a qualified analog product. Every stage is classified as
`pass`, `engineering_only`, `not_run`, `not_applicable`, `blocked`, or `fail`;
the release gate rejects every status other than `pass` or justified
`not_applicable`, and also rejects `release_status: blocked`.

Run the inventory gate from the repository root:

```bash
python3 flow/scripts/signoff/check_analog_signoff_manifest.py \
  --mode inventory \
  --manifest flow/qualification/analog_signoff_manifest.json
```

The current inventory result is `PASS`: every referenced repository artifact
exists and is non-empty. The release gate is intentionally incomplete:

```bash
python3 flow/scripts/signoff/check_analog_signoff_manifest.py \
  --mode signoff \
  --manifest flow/qualification/analog_signoff_manifest.json \
  --output /tmp/tr1um-analog-signoff.json
```

The current result is `INCOMPLETE`; this is the expected safe result while
design-specific analog evidence is absent. It must not be changed to
`release_status: ready` by editing the manifest.

### Temperature and model scope

The temperature release contract intentionally narrows the validated scope to
`27..85 degC`. This is a release-scope change; it does not establish that the
original `-40..85 degC` product requirement is safe.

| Quantity | Declared range |
|---|---:|
| Release operating temperature | `27..85 degC` |
| RS characterization range | `25..150 degC` |
| Manual MOS device guarantee | `-40..150 degC` |

The model/manual reference-temperature distinction is explicit:

- `27 degC` is the model `tnom` and the reference temperature in the manual's
  SPICE model table.
- `25 degC` is retained only as the manual device-characteristic measurement
  condition.
- The audit rejects a source model whose numeric `tnom` does not match `27
  degC`; it does not silently normalize the `25`/`27 degC` distinction.

Run the static audit and the model-level temperature sweep as follows:

```bash
python3 flow/scripts/signoff/audit_temperature_models.py \
  --contract flow/qualification/temperature_model_contract.json \
  --output /tmp/tr1um-temperature-model-audit.json

python3 flow/scripts/signoff/run_temperature_validation.py \
  --contract flow/qualification/temperature_model_contract.json \
  --output flow/qualification/reports/temperature-validation/temperature_validation.json \
  --ngspice ngspice

python3 flow/scripts/signoff/run_pvt_sta.py \
  --manifest <pvt_manifest.json> \
  --output-dir /tmp/tr1um-pvt \
  --sta-bin <opensta>
```

The checked-in temperature report sweeps `27`, `85`, and `150 degC`. The
release-range checks are `27..85 degC`; `150 degC` is included only to exercise
the documented upper model-characterization endpoint. The RS contract is now
`not_needed` for below-25 degC extrapolation because the release range is
inside the declared `25..150 degC` RS characterization range.

The static audit covers `PMOS_mst`, `NMOS_mst`, `MPE_mst`, `MNE_mst`, `F_RR`,
`F_RS`, `m_CSIO`, `DN`, and `DP`. The ngspice probes pass for all executable
models: 12 MOS probes, 15 F_RR probes, 36 F_RS probes, and 6 diode probes.
The report records no low-temperature RS comparison because it is outside the
27..85 degC release scope.

`F_RS` remains `nominal_only`: the source has `tnom=27` but no `temper` term.
Its 27/85/150 degC probes execute successfully, but this is not evidence of a
measured RS temperature coefficient. The narrowed range removes the below-25
extrapolation requirement; the contract records the nominal-only behavior as a
warning rather than a release blocker.

`m_CSIO` is handled the same way under an explicit `temperature_policy:
warning_only` contract entry. The checked-in source declares
`.model m_CSIO C tnom=27`, but has no `TC1`/`TC2` or other machine-readable
temperature law, and the C2 expression is a Spectre-style behavioral
capacitance dependent on geometry and voltage. Ngspice documents that
capacitor temperature behavior requires `TC1`/`TC2`; their absence is not
evidence that the physical capacitance temperature coefficient is zero:

- [ngspice capacitor syntax](https://nmg.gitlab.io/ngspice-manual/circuitelementsandmodels/elementarydevices/capacitors.html)
- [ngspice semiconductor capacitor model](https://nmg.gitlab.io/ngspice-manual/circuitelementsandmodels/elementarydevices/semiconductorcapacitormodel_c.html)
- [MOS capacitor zero-temperature-coefficient reference](https://iopscience.iop.org/article/10.1143/JJAP.30.917)

The temperature report is now `PASS_WITH_WARNINGS`, not `ENGINEERING_ONLY`.
The warnings are explicit: F_RS and CSIO are nominal-only, and CSIO is
audited statically because the checked-in source is Spectre-style. This does
not claim a measured CSIO temperature coefficient. A separate repository issue
also reports numerical convergence risk in the C2 square-root expression near
`v(minus,sub) = -0.61/-0.71 V`: [F_CSIO ngspice issue #96](https://github.com/OpenSUSI/TR-1um/issues/96).
That is a runtime robustness warning, separate from temperature qualification.

### PVT, pseudo-Monte Carlo, and sensitivity analysis

The variation contract at
`flow/qualification/variation_analysis_contract.json` drives
`flow/scripts/analysis/run_variation_analysis.py`. It uses real ngspice
executions for a compact-model probe. A complete execution is reported as
`PASS_WITH_WARNINGS`: `execution_status` remains `PASS`, while the declared
reference-only boundaries are warnings rather than blockers.

```bash
python3 flow/scripts/analysis/run_variation_analysis.py \
  --contract flow/qualification/variation_analysis_contract.json \
  --output flow/qualification/reports/variation-analysis/variation_analysis.json \
  --ngspice ngspice
```
The reference report runs:

- 30 PVT cases: `TT`, `FF`, `SS`, `FS`, and `SF` crossed with
  `4.5/5.0/5.5 V` and `27/85 degC`.
- 64 seeded pseudo-Monte Carlo samples for `V_th`, `mu_0`, and `R_sq`
  proxies, using reference-only bounded normal distributions and an explicit
  independent correlation assumption.
- One-factor-at-a-time low/nominal/high sensitivity for device, interconnect,
  supply, and temperature parameters, plus the existing GND-return bridge
  estimate. These are reference-only local effects.

For routed timing sensitivity, run the existing SPEF perturbation in the
LibreLane development shell so the shell-provided `sta` is used:

```bash
cd "$HOME/Documents/librelane"
nix-shell --run 'cd "$HOME/Documents/TR-1um" && python3 flow/scripts/analysis/rc_sensitivity.py \
  --spef flow/designs/tr1um_alu8/runs/audit-pr1-final2/final/spef/tr1um_alu8..spef \
  --lib flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell_access/lib/TR-1um_stdcell_access_typ_5p0V_25C.lib \
  --netlist flow/designs/tr1um_alu8/runs/audit-pr1-final2/final/pnl/tr1um_alu8.pnl.v \
  --sdc flow/designs/tr1um_alu8/constraints.sdc \
  --top tr1um_alu8 \
  --sta sta \
  --n 20 \
  --seed 20260905 \
  --out /tmp/tr1um-alu8-rc-sensitivity-nix \
  --json-out flow/qualification/reports/variation-analysis/rc_timing_sensitivity_alu8.json'
```

The checked-in timing report has 20/20 finite OpenSTA WNS results with no
negative samples. It is accepted as a reference-only warning: a nominal-corner
RC perturbation screen that does not provide process-qualified Liberty corners,
analog operating points, RF metrics, or signoff timing closure.

Each timing-sensitivity sample reports `r_factor`, `c_factor`,
`critical_path_delay_ns`, and `wns`. The report also emits
`delta_t_r_ns` for the R-only perturbation, `delta_t_c_ns` for the C-only
perturbation, `delta_t_rc_ns` for the coupled perturbation, and
`delta_t_interaction_ns` for the residual RC interaction. All deltas are
relative to the unscaled nominal SPEF baseline.
`critical_path_delay_ns`, `wns`, and all delta fields are reported in ns;
`wns_ns` is an explicit alias of `wns`.

The process corners are synthetic reference modifiers: threshold shifts, `u0`
scales, and `F_RS` resistance scaling. No official FF/SS/FS/SF model cards
exist for this reference flow, so these are accepted warnings. The report is
`PASS_WITH_WARNINGS` when all declared probe executions pass. The GND-return
result is a first-order `I_leak * R_bridge` sensitivity using the existing
leakage-only PDN observation; it does not close the PDNSim/EM/IR TODO or
establish ground-bounce margin.

The sensitivity ranking is local and one-factor-at-a-time. It is not a
multivariate worst-case analysis and does not replace qualified timing,
analog-performance, mismatch, EM, or IR evidence.

### TR-1um electrical-limit contract

The machine-readable electrical limits are centralized in
`flow/qualification/tr1um_electrical_limits.json`. They are sourced from
`openIP62/IP62/Technology/doc/OS00_リファレンスマニュアル_rev1.1.pdf`;
the page numbers and table identifiers are recorded in the contract itself.
They are absolute maximum constraints, not recommended operating targets.
Simulation assertions therefore require an explicit non-zero margin below each
maximum, and the contract remains `engineering_only` until the limits are
correlated with qualified models and silicon evidence.

| Device or structure | Enforced absolute limit | Manual source |
|---|---|---|
| 5V NMOS | `abs(VDS) <= 8 V`; `abs(VGS) <= 15 V` | p. 7, Table I-2-2 |
| 5V PMOS | `abs(VDS) <= 8 V`; `abs(VGS) <= 15 V` (manual values `-8/-15 V`) | p. 7, Table I-2-2 |
| RR/RN/RNHV | terminal-to-terminal `abs(V) <= 27 V`; island-to-P-well `abs(V) <= 100 V` | pp. 7, 9, Tables I-2-2/I-2-4 |
| RR island-to-lower-terminal | **unknown; fail closed** | p. 7 table entry is non-public |
| RS | terminal-to-terminal `abs(V) <= 6 V`; `abs(I) <= 10 mA` | pp. 7, 9, Tables I-2-2/I-2-4 |
| Generic C | upper-to-lower `abs(V) <= 15 V`; lower-electrode-to-P-well `abs(V) <= 50 V` | p. 7, Table I-2-2 |
| DP/DN | reverse `abs(V) <= 10/13 V` | p. 7, Table I-2-2 |
| CSIO characterization | terminal-to-terminal `abs(V) <= 5.75 V`; reverse `abs(V) <= 50 V` | p. 10, Table I-2-5 |

The generic C entry and the CSIO characterization entry are retained
separately; neither silently replaces the other. Likewise, the user-suggested
27 V RR island-to-terminal value is not encoded because the manual does not
publish that entry. `P-substrate` and `PW/P-sub` tie policy remains the manual's
ground-referenced contract; a missing or unknown body/well limit is never
treated as safe.

The wiring/current limits are tied to the manual reference geometries:

| Structure | Reference geometry | Continuous or step limit |
|---|---:|---:|
| M1 | width `2 um` | `900 uA` continuous |
| M2 | width `3 um` | `3.7 mA` continuous |
| M1 step | width `2 um` | `500 uA` |
| TC | `1.4 um` square contact | `780 uA/contact`; instantaneous `7.8 mA/contact` |

The contract deliberately permits no silent width scaling. A current report
must state the exact reference width/size and bind its `limit_ref` to the
central contract. Unknown values fail closed. It also publishes engineering-only
current-density screening values derived from each manual reference
current/width pair. For a step assertion,
`required_width_um = I_peak / J_max_step_coverage`; for continuous metal, use
the corresponding `current_density_a_per_um`. This screening does not relax
the exact-reference-width signoff rule.

### Electrical ERC and netlist-label gate

`libs.tech/klayout/tech/drc/03_Electrical.drc` remains the physical electrical
ruleset. It consumes text on TR-1um label layers `M1/LABEL` (`48/0`) and
`M2/LABEL` (`49/0`) and checks floating gates, substrate connections, and
antenna paths. The deterministic bridge
`flow/scripts/signoff/check_netlist_labels.py` compares those labels with the
exact top `.SUBCKT` interface and verifies that each checked label is anchored
on M1 or M2. The default `top` scope accepts labels inherited through the
physical boundary hierarchy while ignoring unrelated internal cell labels;
unknown labels directly on the top cell fail unless explicitly allowed.

For mixed-voltage layout, the electrical ruleset consumes project-owned
annotation overlays `V15_MARKER` (`150/0`) and `V27_MARKER` (`151/0`), declared
in `tr1um_electrical_limits.json` and visible in `TR-1um.lyp`. With markers
present, KLayout checks 15 V NW-to-normal-NW spacing (`3.5 um`), 27 V
NW-island-to-Pwell spacing (`5 um`), and 15 V marked-M1 width (`2 um`).
Markers are not foundry mask layers and an absent marker cannot be treated as
proof of a voltage class.

Run the label gate before LVS:

```bash
python3 flow/scripts/signoff/check_netlist_labels.py \
  --layout <framed.gds> \
  --top-cell <top_cell> \
  --netlist <top.cir> \
  --output /tmp/netlist-labels.json
```

When `power_nets` is present in the ERC contract, the contract must also
provide `power_net_via_minimums` with exactly one integer minimum (at least
`2`) for every power net. Pass that contract to the label gate:

```bash
python3 flow/scripts/signoff/check_netlist_labels.py \
  --layout <framed.gds> \
  --top-cell <top_cell> \
  --netlist <top.cir> \
  --erc-contract <erc_contract.json> \
  --output /tmp/netlist-labels.json
```

The gate counts unique V1 shapes intersecting the labeled M1/M2 geometry and
aggregates the count at net level. Direct-M2 labels can therefore have zero
local V1 shapes when other labels on the same `Power_Nets` net provide the
required redundant vias. This is a connectivity/redundancy screen, not an
EM-current or via-reliability proof.

The netlist-aware ERC wrapper then requires the label report, the electrical
ruleset, and an explicit rating inventory. Each `rating_bindings` item must
name an instance, declare its device kind (`mos_5v_nmos`, `mos_5v_pmos`, `rr`,
`rs`, `c`, `dp`, `dn`, or `csio`), and reference only limits in that kind's
central-contract namespace:

```bash
python3 flow/scripts/signoff/check_analog_erc.py \
  --contract <erc_contract.json> \
  --report /tmp/drc.lyrdb \
  --ruleset libs.tech/klayout/tech/drc/run.drc \
  --electrical-ruleset libs.tech/klayout/tech/drc/03_Electrical.drc \
  --limits-contract flow/qualification/tr1um_electrical_limits.json \
  --label-report /tmp/netlist-labels.json \
  --output /tmp/erc.json
```

The physical wrapper always runs `check_netlist_labels.py` after drawing DRC
and before LVS. When a signoff manifest is supplied, `ERC_CONTRACT` (or
`ANALOG_ERC_CONTRACT`) is mandatory; the wrapper then runs the netlist-aware
ERC checker with the central limits contract. Intermediate structural runs
without a manifest may omit the supplemental contract, but that mode cannot
produce a manifest-backed ERC pass.

#### Final framed mixed-signal ERC run

The final framed `gc-diode-repair13` netlist/GDS pair was checked with the
contract in `flow/qualification/tr1um_mixed_counter_erc_contract.json`:

```bash
python3 flow/scripts/signoff/check_netlist_labels.py \
  --layout /tmp/tr_1um_mixed_counter_gc_diode_repair13.gds \
  --top-cell tr_1um_mixed_counter \
  --netlist /tmp/gc-diode-repair13-strict-current.cir \
  --erc-contract flow/qualification/tr1um_mixed_counter_erc_contract.json \
  --output /tmp/tr1um-final-erc/netlist_labels.json

python3 flow/scripts/signoff/check_analog_erc.py \
  --contract flow/qualification/tr1um_mixed_counter_erc_contract.json \
  --report /tmp/tr1um-lvs-parity-signoff/drc.lyrdb \
  --ruleset libs.tech/klayout/tech/drc/run.drc \
  --electrical-ruleset libs.tech/klayout/tech/drc/03_Electrical.drc \
  --limits-contract flow/qualification/tr1um_electrical_limits.json \
  --label-report /tmp/tr1um-final-erc/netlist_labels.json \
  --output /tmp/tr1um-final-erc/erc.json
```

Both gates returned `PASS` (`RC=0`). The label gate found top-level ports
`VDD` and `VSS`, and counted `1713` unique V1 shapes on `VDD` against the
contract minimum of `2`.

The persisted ERC result is:

| Field | Result |
|---|---:|
| Contract-aware ERC | `PASS` |
| Hard report items | `0` |
| Warnings | `0` |
| Acknowledged warnings | `0` |
| ERC errors | `0` |

Warning review is complete: `warnings=[]`, so no warning category or message
was emitted and no warning waiver/acknowledgment was accepted.

The ERC stage remains engineering-only because the central limits and analog
qualification are engineering-only. The exact report is bundled at
`flow/qualification/reports/gc-diode-repair13/erc.json`; the source framed
inputs remain intermediate `/tmp` evidence.


### Pre-layout/post-layout simulation assertions

`flow/scripts/signoff/run_analog_sim.py` accepts both `pre_layout` and
`post_layout` cases. Every case still requires the full supply, temperature,
process, load, input-slew, startup, and activity sweep axes, and every case
must declare assertions with a target, measured quantity, central `limit_ref`,
mode, and `0 < margin_fraction < 1`:

```json
{
  "stage": "pre_layout",
  "assertions": [
    {
      "name": "M1_vds_abs",
      "target": "M1",
      "measure": "m1_vds_peak",
      "expression": "v(d_node,s_node)",
      "message": "BVDS Limit Exceeded!",
      "limit_ref": "device_limits.mos_5v_nmos.vds_abs_max_v",
      "mode": "absolute",
      "margin_fraction": 0.10
    },
    {
      "name": "M1_vgs_abs",
      "target": "M1",
      "measure": "m1_vgs_peak",
      "expression": "v(g_node,s_node)",
      "message": "BVGS Limit Exceeded!",
      "limit_ref": "device_limits.mos_5v_nmos.vgs_abs_max_v",
      "mode": "absolute",
      "margin_fraction": 0.10
    }
  ]
}
```

`absolute` compares the absolute value of the runtime expression; `signed`
preserves polarity for a directional assertion. The runner writes a temporary
instrumented deck containing `run`, `let`, `meas tran`, and `if`/`quit 1`
commands, and retains that deck and log in the output directory. An explicit
expression is required because ngspice-47 parses the proposed
`.assert ... alert=fail` form as an undefined parameter. The post-run parser
still records the declared `measure` separately, but the enforced value is the
runtime waveform maximum.
The runner compares the observed value to
`limit * (1 - margin_fraction)`, records both values, and fails on a missing
measurement, missing limit, or over-limit result. Post-layout cases must name
the extracted SPICE deck; the runner never manufactures extraction or models.

For a current assertion, add `width_um` and a central
`density_limit_ref`, for example
`interconnect_limits.metal.M1.current_density_a_per_um` or
`interconnect_limits.steps.M1.j_max_step_coverage_a_per_um`. The runner then
enforces both `I_peak < I_max` after the required margin and
`width_um >= I_peak / J`, where `J` is the selected central density, recording
`required_width_um`. Use the step density for a step/discontinuity assertion;
use the continuous metal density for a continuous segment.

### PDN/EMIR current checks

For a powered contract, `flow/scripts/signoff/check_pdn_contract.py` requires
the central limits contract and `required_interconnect_checks` to list exactly
`metal:M1`, `metal:M2`, `step:M1`, and `contact:TC`. The numeric PDN/EMIR report
must include explicit `interconnect_checks` for each M1/M2 continuous segment,
M1 step, and TC contact. Metal and step records report `width_um`,
`peak_current_a`, and an exact `limit_ref`; contact records report the exact
`size_um`, contact count, steady current per contact, instantaneous current per
contact, and both central limit references. Reference-width mismatch, absent
checks, non-finite values, or either current at/above its manual limit fail
closed. Metal and step records also require `width_um >= peak_current_a / J`,
where `J` is the central continuous-metal density or step-coverage density;
the step diagnostic uses `I_peak/J_max_step_coverage`. The exact reference
width remains mandatory, so this engineering screen cannot waive it. The
generic IR-drop/current-density/via limits remain contract-owned alongside
these process-specific checks.

The checked-in `pdn_emir_contract.json` remains a ground-only
`engineering_only` contract, but the evidence is now explicit in
`reports/pdn-emir/pdn_emir.json`: it records the bridge estimate, the
leakage-only nominal power observation, the powered-core PDNSim failure, and
the 11-design digital inventory. The report deliberately does not claim a
numeric return-path, IR-drop, ground-bounce, electromigration, or
current-density result. `post_layout_sim_manifest.json` remains blocked with
zero cases. These classifications are intentional: machine-readable limits
and connectivity diagnostics are not EM/IR or analog simulation closure.

### Analog robustness contracts

Each checker below validates a design-owned JSON contract and writes a
machine-readable report. A checker PASS is meaningful only when the contract
contains real design evidence; the checked-in current contracts are explicit
blocked placeholders.

| Concern | Checker | Contract |
|---|---|---|
| PDN/EMIR | `flow/scripts/signoff/check_pdn_contract.py` | `flow/qualification/pdn_emir_contract.json` |
| Post-layout simulation | `flow/scripts/signoff/run_analog_sim.py` | `flow/qualification/post_layout_sim_manifest.json` |
| Crosstalk | `flow/scripts/signoff/check_crosstalk.py` | `flow/qualification/crosstalk_contract.json` |
| Latch-up | `flow/scripts/signoff/check_latchup.py` | `flow/qualification/latchup_contract.json` |
| Matching/overdesign | `flow/scripts/signoff/check_matching.py` | `flow/qualification/matching_contract.json` |
| Pad ESD | `flow/scripts/signoff/check_esd.py` | `flow/qualification/esd_contract.json` |
| MOS/poly capacitance | `flow/scripts/signoff/check_capacitance.py` | `flow/qualification/capacitance_contract.json` |

The contract requirements are deliberately explicit:

- PDN/EMIR requires actual PG geometry, voltage sources, current envelopes,
  IR/EM limits, and a zero-violation report for powered macros. A ground-only
  leaf may mark powered PDN not applicable, but its return path remains a
  separate review.
- Post-layout simulation requires extracted SPICE, macro CDL, process models,
  frame/pad/ESD models, digital abstractions, supply/temperature/process/load/
  slew/startup/activity sweeps, and measured limits.
- Crosstalk requires every sensitive victim's extracted coupling, victim
  capacitance, aggressor step/driver/rise data, measured glitch/settling/
  delay/functional-error values, and limits. The checker also reports a
  first-order capacitive bound; it does not infer coupling from layer names.
- Latch-up requires well/substrate topology, tap and guard-ring continuity
  and resistance, positive/negative injection paths, I/O/ESD interactions,
  substrate-current assumptions, and numerical limits. Geometry DRC is not a
  latch-up result.
- Matching requires per-group common-centroid/interdigitation or an explicit
  alternative, dummies, orientation, symmetric routing, surroundings,
  guard-ring evidence, W/L/finger/multiplicity, headroom, current density,
  area, and either valid sigma data or a clearly marked engineering guardband.
- ESD requires every external pad's positive and negative discharge paths,
  VDD/VSS clamps, body/trigger nets, package assumptions, and evidence through
  schematic, CDL, LVS, GDS, and parasitic views.
- Capacitance separates intrinsic MOS, CSIO/F_CSIO, and Poly_cap/CAP. It
  requires area/perimeter, device identity, and extracted-versus-expected
  values over voltage, temperature, and process corners. Unsupported
  Poly_cap/CAP is recorded as unsupported; a PCell coefficient alone is not
  qualification.

The repaired mixed-signal physical wrapper remains usable as an intermediate
structural gate. Supplying the fifth argument enables the analog release
gate, which currently exits with `15` and `INCOMPLETE` after the physical
stages:

```bash
RCX_DEF="$PWD/flow/designs/tr1um_mixed_counter/runs/gc-diode-repair13/final/def/tr1um_mixed_counter.def" \
bash flow/scripts/signoff/run_tr1um_signoff.sh \
  /tmp/tr_1um_mixed_counter_gc_diode_repair13.gds \
  tr_1um_mixed_counter \
  /tmp/gc-diode-repair13-strict-current.cir \
  /tmp/tr1um-release-gate \
  flow/qualification/analog_signoff_manifest.json
```

The no-manifest invocation documented above remains structural/engineering
evidence only. It must not be reported as general analog signoff.

## Final cleanup and optional auxiliary cells

The ALIGN-generated standard-cell library and its dedicated LibreLane
configuration are not in the active default PDK tree. Historical run
directories remain as evidence. The default digital library is
`TR-1um_stdcell`.

The native IP62 source cells `INV_X1`, `NAND2`, `NOR2`, `DFFR`, and `DFFS` each
pass independent cell-level KLayout drawing DRC with zero items. This does not
make the top-level OpenROAD output clean: router access to fixed IP62 pin
geometry still creates top-level DRC errors. The DRC repair must preserve the
foundry rules and solve pin access, row geometry, and top-level power routing.

The optional `KoheiUchi/TR_1um_sc` collateral remains staged outside the
default cell contract. It requires real timing characterization and independent
qualification before enabling.

## ALIGN hard-macro handoff

ALIGN-generated analog cells are integrated as hard macros, not standard cells.
The macro handoff requires a reviewed GDS/LEF pair, explicit macro placement,
abstracted signal/power pins, and a top-level netlist contract. The macro views
must independently pass drawing DRC, strict LVS, MDP, and mask-layer DRC before
being used in a mixed top-level design. The checked-in Magic technology is
diagnostic-only for this handoff.

### Reproducible ALIGN invocation

Enter an environment containing both ALIGN and KLayout, or provide explicit
paths through `CONDA_PY` and `KLAYOUT_BIN`. The runner accepts a netlist
basename or an absolute path and normalizes it before invoking ALIGN:

```bash
bash flow/scripts/align/run_align_tr1um.sh \
  flow/align_test/input \
  telescopic_ota \
  telescopic_ota_tr1um.sp \
  /tmp/tr1um-align-work
```

The runner now:

- fails closed for missing inputs and propagates ALIGN exceptions;
- resolves KLayout instead of assuming it is on `PATH`;
- emits canonical `TELESCOPIC_OTA.gds` and `TELESCOPIC_OTA.lef` names;
- uses the checked-in external placement for `TELESCOPIC_OTA` by default,
  bypassing the installed ALIGN CBC placement stall;
- leaves generic designs on the normal ALIGN placer; and
- supports `ALIGN_REQUIRE_CLEAN=1`, which runs the TR-1um drawing DRC and
  fails on any ALIGN-reported or KLayout-reported item.

### Current ALIGN reproduction status

The full OTA flow now completes deterministically in approximately ten seconds
and produces valid canonical GDS/LEF output. The minimal `mirror.sp` control
case also completes with the normal placer. The previous unbounded OTA run
stalled in ALIGN's C++ CBC/CLP aspect-ratio ILP because no external placement
was supplied.

The generated OTA view is **not yet signoff-clean**. The latest verified KLayout
drawing DRC (with ALIGN's default three dummy gates per side restored for the
analog primitives) reports 33 items:

- `CO.GG`: 12
- `CO.SM`: 9
- `CO.Z1`: 12

This is down from the earlier compacted one-dummy variant (37 items). Per-cell
checks: `DP_NMOS_B_48288725_X1_Y1` 7 items, `CMC_S_NMOS_B_31116170_X1_Y1`
6 items, `CMC_PMOS_12845765_X1_Y1` 7 items - the same three FEOL contact
categories. `ALIGN_REQUIRE_CLEAN=1` correctly exits nonzero rather than hiding
these violations. No DRC rule is weakened and no report is waived.

The errors originate in the TR1um ALIGN primitive geometry/contact abstraction,
not in the runner or placement hang. Individual generated primitives reproduce
the same contact-rule failures before top-level assembly. The generated layout
places diffusion contacts on M1 tracks 2 um from the gate-poly edges, while the
legal foundry reference (`INV_X1`) keeps contact spacing exactly 1.0 um from
gate edges in dedicated columns. The ALIGN grid abstraction (M1 pitch 7 um)
cannot express the 1.0 um contact offset, so legal contacts require a custom
primitive FEOL layout or the use of the qualified IP62/access standard-cell GDS
as primitive masters. Multiple contact-row, gate-pad, V0-spacing, dummy-gate,
and shared-diffusion sweeps were run; none reached zero. The next required
repair is legal primitive contact placement, and a clean regenerated OTA view.

The macro-level signoff runner remains opt-in until the drawing DRC is clean.
The OTA handoff remains blocked until finalized, qualified top-level physical
views are available.

The runner's diagnostic controls are:
`ALIGN_FLOW_START`, `ALIGN_FLOW_STOP`, `ALIGN_EXTERNAL_PLACEMENT`,
`ALIGN_EFFORT`, `ALIGN_ROUTER_MODE`, `ALIGN_ROUTER`, `ALIGN_SEED`,
`ALIGN_REQUIRE_CLEAN`, and `ALIGN_DRC_RUNSET`.

The analytical placer is not used as a workaround; the installed ALIGN build
segfaults on this OTA when that path is selected.
The macro-level signoff runner is available only as an opt-in diagnostic. A
focused native `INV_X1` proof passed drawing DRC, strict LVS, and mask DRC with
one documented warning; this validates runner behavior, not mixed top-level
signoff.

Using the checked-in technology LEF gives:

| Layer | Nominal width | R_sheet | R' | C' |
|---|---:|---:|---:|---:|
| M1 | 1.8 µm | 0.050 Ω/□ | 0.0277778 Ω/µm | 0.1630 fF/µm |
| M2 | 3.0 µm | 0.030 Ω/□ | 0.0100000 Ω/µm | 0.1525 fF/µm |

The estimate uses ±50% engineering sensitivity bands for sheet resistance and
capacitance. Via resistance is not published and the current OpenROAD LEF
reports 0 Ω for V1; this is an explicit limitation, not a measured value.
`flow/scripts/analysis/rc_sensitivity.py` can perturb SPEF R/C values deterministically
for timing sensitivity checks. Estimated RCX is acceptable for flow timing
closure and engineering comparison, but not by itself for tapeout signoff.

## Closure audit

The current integrated evidence is:

- `flow/designs/tr1um_counter/runs/access-canonical-final`: 12 mapped
  instances, zero route DRC errors, zero digital KLayout DRC items, zero
  setup/hold WNS/TNS, and zero disconnected-pin metrics after the checker fix.
- `flow/signoff/tr_1um_counter_access_canonical.gds`: passes the framed MPW
  structural precheck with the required `tr_1um_` top-cell name, 0.001 um dbu,
  exact 2500 × 2500 um bbox, and `OSS_FRAME` hierarchy.
- `/tmp/tr1um-final-mpw`: independent pre-LVS evidence with zero hard drawing
  items, zero hard IP62 items, and a non-empty MDP GDS. The IP62 report
  contains 20 `WAR06` informational entries.
- `/tmp/tr1um-current-final`: current full-wrapper evidence with structural
  precheck, drawing DRC, strict LVS, MDP, mask DRC, and the accepted RCX value
  all passing. The wrapper now supplies the RCX command automatically when no
  override is provided.

The accepted RCX recipe is the repository's TR-1um foundry-flow value. A real
foundry RCX deck is unavailable and is not required by this integration policy.
Native top-level LibreLane DRC remains a reference diagnostic; MPW framed DRC,
strict LVS, accepted RCX, and the corrected disconnected-pin checker are the
active signoff surfaces.

No DRC rule was weakened and no timing violation was waived.
