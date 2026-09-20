# Reusable GDS-to-Parasitics Flow

This directory contains an extraction-only flow for turning a layout cell into an engineering post-layout SPICE representation. It is intentionally separate from ordinary DRC/LVS qualification.

## Entry points

- `extraction.lvs`: standalone KLayout extraction runset.
- `gds_to_parasitics.py`: command-line orchestrator for connectivity extraction, DEF bridge generation, RC extraction, and post-layout netlist assembly.
- `extract_tr1um_parasitics.py`: existing TR-1um DEF/SPEF parasitic extractor.
- `build_postlayout_spice.py`: existing device/parasitic netlist merger.

`extraction.lvs` stages the PDK DRC/LVS collateral into the run output and invokes KLayout's net-only connectivity extraction. It does not replace or modify the ordinary LVS runset.

## Inputs

Required:

- GDS layout and top cell: `--gds`, `--top`
- RC model JSON: `--rc`
- output directory: `--output-dir`

Optional audit and merge inputs:

- source SPICE: `--source-spice` or `--spice`
- Xschem symbol: `--xschem-sym` or `--sym`
- explicit compatible reference netlist: `--reference-netlist`, `--reference-top`
- technology collateral root: `--tech-root`
- KLayout execution through Nix: `--nix-shell`, `--nix-shell-cwd`

## Example invocation

```bash
python3 flow/scripts/analysis/gds_to_parasitics.py \
  --gds path/to/layout.gds \
  --top TOP_CELL \
  --rc path/to/rc_estimate.json \
  --source-spice path/to/source.spice \
  --xschem-sym path/to/TOP_CELL.sym \
  --output-dir path/to/pex-output \
  --tech-root /path/to/TR-1um/libs.tech/klayout/tech \
  --nix-shell \
  --nix-shell-cwd /path/to/librelane
```

The command is deterministic with respect to its input paths and writes all generated collateral below `--output-dir`.

## Data flow

1. KLayout extracts the top-cell connectivity from the GDS.
2. The runset emits a connectivity report and an engineering DEF bridge.
3. The bridge preserves exact-net polygon connectivity across M1, V1, and M2 and exposes only actual top-level pins.
4. The existing TR-1um parasitic extractor generates SPEF, interconnect SPICE, and a machine-readable parasitic ledger.
5. The existing post-layout merger combines the physical interconnect with the extracted device netlist.
6. The orchestrator writes an audit manifest and records whether the result is complete or partial.

Physical KLayout connectivity is authoritative. Source SPICE and Xschem symbols are used for audit and optional compatible-netlist merging; they do not override a physical short or rename a physical net.

## Outputs

For top cell `TOP_CELL`, the output directory contains the following artifacts when each stage succeeds:

- `TOP_CELL.gds_connectivity.def`
- `TOP_CELL.gds_connectivity.json`
- `TOP_CELL.klayout.extracted`
- `TOP_CELL.parasitics.spef`
- `TOP_CELL.interconnect.sp`
- `TOP_CELL.parasitics.json`
- `TOP_CELL.postlayout.sp`
- `TOP_CELL.devices.sp` and `TOP_CELL.devices.json`
- `TOP_CELL.pex_manifest.json`
- `TOP_CELL.extraction_flow.json`
- stage logs for KLayout, parasitic extraction, and post-layout merging

The final manifest is the machine-readable handoff. It records input paths, physical/source/symbol pin audits, stage status, output paths, node and edge counts, and warnings.

## Port and merge rules

- Top-level KLayout pins are exported into the DEF bridge; internal named nets are not promoted to external pins.
- Pin-set audits are case-insensitive for ordinary net-label casing differences.
- A source netlist is not used as the default physical connectivity reference. Use `--reference-netlist` only when its top-cell port mapping is independently known to match the extracted physical netlist.
- `--allow-partial` permits an incomplete engineering artifact for debugging; it does not turn the result into a qualified extraction.

## Qualification boundary

The flow reports `engineering_estimate_not_foundry_qualified` by default. The RC JSON, layer stack, via rules, device models, and generated DEF bridge must be reviewed for the target process before using the result as sign-off evidence. The flow does not claim foundry-calibrated parasitics, LVS equivalence, or silicon correlation.
