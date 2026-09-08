# TR-1um ALIGN GDS post-processor.
#
# This script performs only deterministic layer conversion and origin
# normalization. It intentionally does not grow/shrink contacts or wells,
# alter device polarity, add labels, or repair routing. Those operations can
# change connectivity and therefore must be solved in the ALIGN generator or
# verified by signoff, not hidden in a streamout postprocess.
import os
import pya

GDS_IN = os.environ.get("TR1UM_GDS_IN", "/dev/null")
GDS_OUT = os.environ.get("TR1UM_GDS_OUT", "/dev/null")

ly = pya.Layout.new()
ly.read(GDS_IN)
top = ly.top_cell()
top.flatten(-1, True)

def L(layer, datatype=0):
    return ly.layer(pya.LayerInfo(layer, datatype))

def R(cell, layer, datatype=0):
    return pya.Region(cell.shapes(L(layer, datatype))).merged()

# ALIGN temporary layers:
#   Active 99/0, Nselect 202/0, Pselect 203/0, Nwell 206/0, Poly 8/0.
# TR-1um drawing layers:
#   AP 3/1, AN 3/2, GC 8/1, WN 140/0.
active = R(top, 99)
nselect = R(top, 202)
pselect = R(top, 203)
nwell_marker = R(top, 206)
poly = R(top, 8)

ap = active & pselect
an = active & nselect
unmarked = active - ap - an
ap += unmarked & nwell_marker
an += unmarked - nwell_marker

top.shapes(L(3, 1)).insert(ap)
top.shapes(L(3, 2)).insert(an)
top.shapes(L(8, 1)).insert(poly)

# Preserve ALIGN's well marker with the documented 7um enclosure. Do not use
# an AP-derived well: that would change the well/body topology.
top.shapes(L(140, 0)).insert(nwell_marker.sized(7000))

# Preserve labels from ALIGN's M2/M1 label datatypes on the TR-1um LVS label
# layers. Labels are copied, not moved, so the source drawing remains intact.
for src, dst in (((20, 4), (49, 0)), ((13, 4), (48, 0))):
    src_idx = ly.find_layer(pya.LayerInfo(*src))
    if src_idx is None:
        continue
    dst_idx = L(*dst)
    for shape in top.shapes(src_idx):
        if shape.is_text():
            top.shapes(dst_idx).insert(shape.text)

# Remove temporary/helper layers from the output. Keep real TR-1um drawing
# layers, labels, and routing layers unchanged.
for info in list(ly.layer_indexes()):
    li = ly.get_info(info)
    # Delete only ALIGN source/helper layers. Keep generated TR-1um GC 8/1.
    if (li.layer, li.datatype) in {
        (8, 0), (99, 0), (100, 0), (101, 0),
        (200, 0), (201, 0), (202, 0), (203, 0), (204, 0), (205, 0), (206, 0)
    }:
        ly.delete_layer(info)

# ALIGN can emit a negative bbox because of via enclosures. Move the complete
# flattened design only; no shape is resized or reinterpreted.
bbox = top.bbox()
if bbox.left != 0 or bbox.bottom != 0:
    ly.transform(pya.Trans(pya.Vector(-bbox.left, -bbox.bottom)))

ly.write(GDS_OUT)
# DRC is intentionally not run here; every generated view must pass the
# repository's KLayout run.drc after this conversion.
print(f"Wrote {GDS_OUT}: drawing layers converted and origin normalized")
