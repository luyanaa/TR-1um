# Preface: active TR-1um LVS runset

The tutorial follows the active TR-1um KLayout LVS flow. The wrapper
[`lvs.lylvs`](../../libs.tech/klayout/tech/lvs/lvs.lylvs) delegates to
[`run.lvs`](../../libs.tech/klayout/tech/lvs/run.lvs); the wrapper is not a
second implementation of the runset.

## Active include graph

`run.lvs` includes the shared drawing-layer/device definitions, then the
active extraction, combination, custom reader/writer, and comparison stages:

```ruby
# %include ../drc/00_Layers.drc
# %include ../drc/02_Device.drc
# %include 01_Extract.lvs
# %include 03_Combiner.lvs
# %include 02_Extract.lvs
# %include 04_Custom.lvs
# %include 05_Compare.lvs
```

The old `00_Extract.lvs`/`03_Extract.lvs` examples are not active inputs and
must not be copied into a new runset. The legacy `tech/lvs/IP62` tree is also
not part of the active include graph.

## Runtime controls

The active runset accepts these controls through KLayout `-rd` variables:

- `input` and optional `top_cell`: source GDS and the extraction top cell;
- `report`: output `.lvsdb` report, or the interactive report window when absent;
- `run_mode=flat|deep`: flat extraction is opt-in; deep extraction is default;
- `netlist_only`: extract and write the layout netlist without schematic compare;
- `extracted` and `circuit`: explicit layout-netlist and schematic paths;
- `ignore_top_ports_mismatch`: opt out of strict top-level port checking.

Unless `ignore_top_ports_mismatch` is set, the comparison stage requires both
netlist comparison and `flag_missing_ports`. A clean device comparison with a
missing or renamed top-level port is therefore not an LVS pass.

## Authoritative source files

The examples in the following chapters mirror these files:

- [`01_Extract.lvs`](../../libs.tech/klayout/tech/lvs/01_Extract.lvs): MOS,
  ESD MOS, diode, and global-node extraction;
- [`02_Extract.lvs`](../../libs.tech/klayout/tech/lvs/02_Extract.lvs): CSIO,
  RR, and RS extraction plus parameter contracts;
- [`03_Combiner.lvs`](../../libs.tech/klayout/tech/lvs/03_Combiner.lvs):
  reference-only parallel/series device-combination behavior;
- [`04_Custom.lvs`](../../libs.tech/klayout/tech/lvs/04_Custom.lvs): SPICE
  reader/writer translation for `F_RR`, `F_RS`, and `F_CSIO`;
- [`05_Compare.lvs`](../../libs.tech/klayout/tech/lvs/05_Compare.lvs): strict
  comparison, finite standard-cell flattening, and output generation.
