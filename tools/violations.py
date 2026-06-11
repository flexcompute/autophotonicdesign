"""
Violation overlay: paint WHERE the problems are, so the AI (and the LiveViewer) can see them.

When a chip is dirty, `annotate()` returns a copy with every collision region and KLayout DRC
marker drawn on a bright **VIOLATION** layer over the layout. This is the visual companion to the
numeric reports in tools/validation.py (the LVS guide's `show_collisions()` idea, extended to the
KLayout marker database too).
"""
import re
import xml.etree.ElementTree as ET

import photonforge as pf

from . import validation as V

VIO = "VIOLATION"
VIO_GDS = (1000, 0)


def ensure_layer(tech=None):
    tech = tech or pf.config.default_technology
    if VIO not in tech.layers:
        tech.add_layer(VIO, pf.LayerSpec(layer=VIO_GDS, description="DRC / collision marker",
                                         color="#ff2020cc", pattern="//"))


def parse_drc_markers(lyrdb_path, skip=("Boundary", "Devices")):
    """{rule: [(x0,y0,x1,y1), ...]} bounding boxes for every DRC marker (µm)."""
    out = {}
    try:
        root = ET.parse(str(lyrdb_path)).getroot()
    except Exception:  # noqa: BLE001
        return out
    for item in root.iter("item"):
        rule = (item.findtext("category", "") or "").strip("'\"")
        if rule in skip:
            continue
        nums = []
        for val in item.iter("value"):
            nums += [float(x) for x in re.findall(r"-?\d+\.?\d*", val.text or "")]
        # numbers come in (x, y) pairs across all edges/polys of the marker
        xs, ys = nums[0::2], nums[1::2]
        if xs and ys:
            out.setdefault(rule, []).append((min(xs), min(ys), max(xs), max(ys)))
    return out


def _frame(comp, x0, y0, x1, y1, t):
    """Draw a hollow rectangle frame (thickness t) so the highlighted layout stays visible."""
    comp.add(VIO, pf.Rectangle((x0, y0), (x1, y0 + t)))
    comp.add(VIO, pf.Rectangle((x0, y1 - t), (x1, y1)))
    comp.add(VIO, pf.Rectangle((x0, y0), (x0 + t, y1)))
    comp.add(VIO, pf.Rectangle((x1 - t, y0), (x1, y1)))


def annotate(chip, collisions, drc_lyrdb=None):
    """Return (overlay_component, n_marks): the chip with violations painted on VIOLATION.

    Waveguide/metal overlaps are the EXACT boolean intersection polygons (LVS show_collisions
    style), so the highlight sits precisely on the colliding geometry, not a bounding box.
    """
    ensure_layer()
    v = pf.Component(chip.name + "_VIO")
    v.add_reference(chip)
    n = 0

    # 1) EXACT waveguide + metal-route overlap regions (inter-structure + intra-structure)
    for layer in (V.WG, V.M2):
        regions, _ = V.waveguide_collisions(chip, layer)
        for p in regions:
            v.add(VIO, p)
            n += 1

    # 2) M2-over-M1 heatsink regions (exact boolean polygons, minus intended M_Open contacts)
    m1, m2 = V.layer_polygons(chip, V.M1), V.layer_polygons(chip, V.M2)
    if m1 and m2:
        inter = pf.boolean(m1, m2, "*")
        opens = V.layer_polygons(chip, V.MOPEN)
        if opens and inter:
            inter = pf.boolean(inter, opens, "-")
        for p in (inter or []):
            if abs(p.area()) > 1e-3:
                v.add(VIO, p)
                n += 1

    # 3) bond-pad-pitch violations: mark each too-close pad
    for entry in collisions.bondpad_close_pairs:
        for (cx, cy) in entry[1:3]:
            v.add(VIO, pf.Rectangle((cx - 35, cy - 35), (cx + 35, cy + 35)))
            n += 1

    # 4) KLayout DRC markers (precise locations)
    if drc_lyrdb:
        for rule, boxes in parse_drc_markers(drc_lyrdb).items():
            for (x0, y0, x1, y1) in boxes:
                pad = 1.0  # enlarge sub-µm markers so they are visible
                v.add(VIO, pf.Rectangle((x0 - pad, y0 - pad), (x1 + pad, y1 + pad)))
                n += 1
    return v, n
