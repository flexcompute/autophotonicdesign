"""
Floorplanning: pack self-contained test structures into a fixed-cost die.

Uses photonforge.pack_layout (bin packing). The die area is the fixed budget (25 mm^2 MPW area tier);
pack_layout splits overflow into extra bins, so the count that lands in bin 0 is exactly the
number of structures that fit the die. The agent maximizes that count.

**Same direction for the wafer prober (v1):** packing is translation-only
(`allow_rotation=False` by default and enforced by the loop), so every site keeps the orientation
it was built with — every grating-coupler array faces west, every bond-pad cage faces south. The
`orientation_consistent` gate in validation.py verifies no reference was rotated or reflected.
"""
import photonforge as pf

# chip-outline layers (SiEPIC): "Oxide open to BOX" (6,0) marks the usable die area
DIE_LAYER = "Oxide open to BOX"
FLOORPLAN_LAYER = (99, 0)        # KLayout SiEPIC "FloorPlan"; Si.outside(FP) is the Boundary rule
DICING_LAYER = (6, 1)            # CHIP_EXCLUSION_ZONE: the dicing-street keep-out ring
DICE_MARGIN = 25.0               # um kept clear around the die edge for the dicing saw


def pack_into_die(structures, *, die_w, die_h, gap=30.0, sorting="area", method="blsf",
                  allow_rotation=False, draw_boundary=True, dice_margin=DICE_MARGIN):
    """Pack `structures` into a die of size (die_w, die_h), keeping a `dice_margin` ring clear.

    Structures are packed into the usable area (die minus the dicing ring on all sides), so every
    device ends up >= dice_margin from the die edge. `allow_rotation` defaults False so site
    orientation is preserved (the wafer-prober same-direction rule). Returns (chip, metrics).
    """
    n_total = len(structures)
    usable_w = die_w - 2 * dice_margin
    usable_h = die_h - 2 * dice_margin

    # A structure bigger than the USABLE area can never be placed; treat as spilled, never crash.
    def _fits(s):
        (x0, y0), (x1, y1) = s.bounds()
        w, h = x1 - x0 + gap, y1 - y0 + gap
        if w <= usable_w and h <= usable_h:
            return True
        return allow_rotation and h <= usable_w and w <= usable_h
    fit = [s for s in structures if _fits(s)]

    if fit and usable_w > 0 and usable_h > 0:
        try:
            packs = pf.pack_layout(
                fit, gap=gap, max_size=(usable_w, usable_h),
                sorting=sorting, method=method, allow_rotation=allow_rotation,
            )
        except RuntimeError:
            packs = [pf.Component("PACK_EMPTY")]
    else:
        packs = [pf.Component("PACK_EMPTY")]
    chip = packs[0]
    n_placed = len(chip.references)
    die_area_mm2 = (die_w * die_h) / 1e6

    if n_placed == 0:
        metrics = {
            "n_placed": 0, "n_total": n_total, "n_spilled": n_total, "n_bins": len(packs),
            "die_w_um": die_w, "die_h_um": die_h, "die_area_mm2": die_area_mm2,
            "used_w_um": 0.0, "used_h_um": 0.0, "used_area_mm2": 0.0, "fill_fraction": 0.0,
            "dice_margin_um": dice_margin,
        }
        return chip, metrics

    (x0, y0), (x1, y1) = chip.bounds()   # packed cluster (within usable area)
    used_w, used_h = x1 - x0, y1 - y0
    used_area_mm2 = (used_w * used_h) / 1e6
    placed_area = sum((b1 - b0) * (d1 - d0)
                      for (b0, d0), (b1, d1) in (ref.bounds() for ref in chip.references))
    fill_fraction = placed_area / (die_w * die_h)

    if draw_boundary:
        # die boundary placed so the cluster sits >= dice_margin inside on every side
        dminx, dminy = x0 - dice_margin, y0 - dice_margin
        chip.add(DIE_LAYER, pf.Rectangle((dminx, dminy), (dminx + die_w, dminy + die_h)))
        # FloorPlan = die minus the dicing ring (Si must be inside -> dicing keep-out enforced)
        chip.add(FLOORPLAN_LAYER, pf.Rectangle((dminx + dice_margin, dminy + dice_margin),
                                               (dminx + die_w - dice_margin,
                                                dminy + die_h - dice_margin)))

    right_strip = (usable_w - used_w) * usable_h / 1e6
    top_strip = usable_w * (usable_h - used_h) / 1e6
    metrics = {
        "n_placed": n_placed,
        "n_total": n_total,
        "n_spilled": n_total - n_placed,
        "n_bins": len(packs),
        "die_w_um": die_w, "die_h_um": die_h,
        "die_area_mm2": die_area_mm2,
        "usable_w_um": usable_w, "usable_h_um": usable_h,
        "used_w_um": used_w, "used_h_um": used_h,
        "used_area_mm2": used_area_mm2,
        "fill_fraction": fill_fraction,
        "free_fraction": round(1.0 - fill_fraction, 4),
        "free_right_mm2": round(right_strip, 2),
        "free_top_mm2": round(top_strip, 2),
        "dice_margin_um": dice_margin,
        "allow_rotation": bool(allow_rotation),
    }
    return chip, metrics
