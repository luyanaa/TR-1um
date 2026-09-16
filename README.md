# TR-1um Open Source PDK project (NDA-free 1um CMOS PDK)

The TR-1um Open Source PDK project, a new NDA-Free PDK ecosystem in Japan, is supported by the non-profit OpenSUSI (Open Source Utilized Silicon Initiatives). [**Tokai Rika**](https://tr-semicon.tokai-rika.co.jp/foundry-service) approved to open their PDK and manufacture the data, which is designed by the Open Source EDA tool at Tokai Rika's facility.

The original document and the DRC/LVS runsets are deliverable as-is by Tokai Rika. Yet, the OpenSUSI proposes new PDK package development based on the Drawing layer + MDP (Mask Development Preparation) procedure. Please see [Manifest](Document/Manifesto.md).

**We welcome your feedback and advice.** We are also planning the Shuttle service once any budgets are in place.

# TR-1um Directory Structure 
```
TR-1um -- openIP62 -- AnagixLoader
       |           +- IP62
       +- GDSII
       +- schematic
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

## GDSII
Final GDSII data for 2025/09/24-25 OSS hands-on seminar on Kyushu university.

## schematic
Final schematic data for 2025/09/24-25 OSS hands-on seminar on Kyushu university.

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

### Planned

- Add ESD device checks to DRC/LVS.
- Use `TR-1um_DRC_Regression_TEST` (Cat-1 through Cat-9) as the DRC
  qualification gate before release.
- Add RC/parasitic extraction flow and collateral (OpenRCX or an equivalent
  TR-1um-qualified extractor; layer R/C values, via R/C, SPEF/PEX validation).
- Qualify LibreLane PDN/routing/signoff against the MPW template and the
  TR-1um DRC/LVS/MDP regression before tapeout use.
- Qualify ALIGN-generated analog macros through the MPW pre-check, DRC, LVS,
  MDP, and RC/parasitic extraction flow.
- Fix the TR-1um ALIGN abstraction DRC debt (CO width/enclosure, V1
  enclosure/overlap, off-grid 0.050) in `layers.json`/`mos.py` so generated
  primitives pass the foundry drawing-layer DRC deck.

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
