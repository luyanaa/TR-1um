# TR-1um_stdcell_access library

This is an opt-in derived IP62 BEOL access library. It keeps the source
`STDLIB/LogicCells/gds` geometry and adds per-pin M1/V1/M2 landing patches using
native IP62 dimensions. The library is not the default SCL.

Qualification artifacts are written under `flow/qualification/ip62_beol/` by
`flow/scripts/access/qualify_ip62_beol_cells.py`.
