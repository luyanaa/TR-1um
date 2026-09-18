# Tutorial: active TR-1um KLayout LVS flow

This tutorial explains the active TR-1um LVS runset as a sequence of
maintainable stages. The checked-in runset is authoritative; examples in this
manual are kept synchronized with it and are not a substitute for a KLayout
run.

## Chapters

1. [Preface and active include graph](./LVS00_Prefece.md)
2. [Device and global-node extraction](./LVS01_Chapter.md)
3. [Active layer/connectivity contract](./LVS02_Chapter.md)
4. [Passive extraction and combiner contract](./LVS03_Chapter.md)
5. [Custom reader/writer and strict comparison](./LVS04_Compare.md)

The combiner section is reference-only until a dedicated KLayout regression
fixture covers parallel/series resistor and parallel CSIO behavior. The active
comparison contract still requires strict top-level ports by default.
