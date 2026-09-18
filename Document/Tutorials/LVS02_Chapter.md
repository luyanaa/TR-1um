# Chapter 2: active extraction-layer contract

The active runset separates device recognition from passive extraction:

- [`01_Extract.lvs`](../../libs.tech/klayout/tech/lvs/01_Extract.lvs) handles
  MOS, ESD-MOS, and diodes;
- [`02_Extract.lvs`](../../libs.tech/klayout/tech/lvs/02_Extract.lvs) handles
  CSIO, RR, and RS devices.

This chapter records the shared aliases used by both files. It intentionally
does not reproduce the obsolete `AAMP`/`AAMN`/`SGG`/`NWMP` examples.

## Active recognition aliases

The aliases are defined by the active DRC includes:

```ruby
# 02_Device.drc
MP  = (AP.interacting(GC) & WN - ESD)
MN  = (AN.interacting(GC) & WP - ESD)
MPE = (AP.interacting(GC) & WN & ESD)
MNE = (AN.interacting(GC) & WP & ESD)
DP  = (AP.not_interacting(GC) & WN)
DN  = (AN.not_interacting(GC) & WP)

# 02_Device.drc
SDP  = (MP  - GC)
SDN  = (MN  - GC)
SDPE = (MPE - GC)
SDNE = (MNE - GC)
```

For passive devices, the active layers are `GC`/`AC`/`WC` for CSIO,
`RS`/`RSC` for salicide-gate resistors, and `RR`/`ARC`/`AR`/`WR` for
well resistors. These aliases are generated in `02_Device.drc`; they are not
schematic net names.

## Global and physical connections

The active extraction source makes the substrate contract explicit:

```ruby
# 01_Extract.lvs
connect_global(BULK, "VSS")
connect_global(WN,   "VDD")

# 02_Extract.lvs
connect_global(BULK, "VSS")
connect_global(GN,   "VSS")
```

It also connects recognition layers to contact and routing layers before
extraction. For example, the active device definitions connect `SDP`, `SDN`,
`SDPE`, and `SDNE` to `CO`, then connect `CO` to `M1`, `M1` to `V1`, and `V1`
to `M2`. Copying an old global-only example omits those physical
connectivity rules and does not reproduce the active LVS netlist.

## Scope of this chapter

The examples here describe the active layer vocabulary and connectivity
preconditions. Device parameters, tolerances, equivalent pins, and the
reference-only combiner behavior are shown in
[Chapter 3](./LVS03_Chapter.md), because those contracts are defined beside
the active passive-device extraction source.
