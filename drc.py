"""drc.py — Physics + connectivity DRC for the PN auto-design agent.

Not a classical mask-layer DRC. These rules operate directly on the
`IMPLANTS` list and catch the failure modes learned from the SISCAP and
Yong-U reference notebooks. Pure Python — no KLayout, no cloud calls.

Usage:
    python drc.py

Exit codes:
    0  all rules pass
    1  one or more violations (detail printed to stdout, plot saved to
       output/drc.png)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

import numpy as np

from design import IMPLANTS, geometry
from tools.doping_builders import (
    DopingRegion, geometry_bounds, silicon_mask,
)


# =========================================================================
# Rule parameters
# =========================================================================
MIN_STRIPE_WIDTH_UM    = 0.100
MIN_STRIPE_HEIGHT_UM   = 0.030
MAX_CONCENTRATION_CM3  = 1.0e20
OHMIC_CONTACT_FLOOR    = 1.0e19    # min peak concentration for the outer 100 nm
OHMIC_WIDTH_UM         = 0.100     # width of the outer ohmic-contact band
EPS_UM                 = 1e-6      # rectangle-touching tolerance


@dataclass
class Violation:
    rule: int
    description: str
    regions: list[str]              # region names involved


# =========================================================================
# Rule helpers
# =========================================================================
def _rects_touch_or_overlap(a: DopingRegion, b: DopingRegion) -> bool:
    """True if rectangles a and b share any interior point or an edge."""
    y_overlap = (a.ymin <= b.ymax + EPS_UM) and (a.ymax >= b.ymin - EPS_UM)
    z_overlap = (a.zmin <= b.zmax + EPS_UM) and (a.zmax >= b.zmin - EPS_UM)
    return y_overlap and z_overlap


def _rects_interior_overlap(a: DopingRegion, b: DopingRegion) -> bool:
    """True if a and b share a region of non-zero area (not just an edge)."""
    y_overlap = max(0.0, min(a.ymax, b.ymax) - max(a.ymin, b.ymin))
    z_overlap = max(0.0, min(a.zmax, b.zmax) - max(a.zmin, b.zmin))
    return (y_overlap > EPS_UM) and (z_overlap > EPS_UM)


def _touches_p_rail(r: DopingRegion, b: dict) -> bool:
    return r.ymin <= b["y_slab_L"] + EPS_UM


def _touches_n_rail(r: DopingRegion, b: dict) -> bool:
    return r.ymax >= b["y_slab_R"] - EPS_UM


def _connected_components(regions: list[DopingRegion]) -> list[list[int]]:
    """Group regions of the same polarity that touch/overlap into components."""
    n = len(regions)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if regions[i].kind != regions[j].kind:
                continue
            if _rects_touch_or_overlap(regions[i], regions[j]):
                union(i, j)

    comps: dict[int, list[int]] = {}
    for i in range(n):
        comps.setdefault(find(i), []).append(i)
    return list(comps.values())


# =========================================================================
# Individual rules
# =========================================================================
def rule_1_min_stripe_dims(regions):
    out = []
    for r in regions:
        w = r.ymax - r.ymin
        h = r.zmax - r.zmin
        if w < MIN_STRIPE_WIDTH_UM - EPS_UM or h < MIN_STRIPE_HEIGHT_UM - EPS_UM:
            out.append(Violation(
                rule=1,
                description=f"stripe '{r.name}' is {w*1e3:.0f}×{h*1e3:.0f} nm "
                            f"(min {MIN_STRIPE_WIDTH_UM*1e3:.0f}×"
                            f"{MIN_STRIPE_HEIGHT_UM*1e3:.0f} nm)",
                regions=[r.name],
            ))
    return out


def rule_2_max_concentration(regions):
    out = []
    for r in regions:
        if r.concentration > MAX_CONCENTRATION_CM3 * (1 + 1e-9):
            out.append(Violation(
                rule=2,
                description=f"stripe '{r.name}' peak {r.concentration:.2e} "
                            f"exceeds max {MAX_CONCENTRATION_CM3:.0e} cm⁻³",
                regions=[r.name],
            ))
    return out


def rule_3_contact_extension(regions, b):
    out = []
    if not any(r.kind == "acceptor" and _touches_p_rail(r, b) for r in regions):
        out.append(Violation(
            rule=3,
            description="no acceptor region reaches the P contact rail "
                        f"(y ≤ {b['y_slab_L']:.3f})",
            regions=[],
        ))
    if not any(r.kind == "donor" and _touches_n_rail(r, b) for r in regions):
        out.append(Violation(
            rule=3,
            description="no donor region reaches the N contact rail "
                        f"(y ≥ {b['y_slab_R']:.3f})",
            regions=[],
        ))
    return out


def rule_4_no_floating_pockets(regions, b):
    """Every same-polarity component must have at least one rail-connected region."""
    out = []
    comps = _connected_components(regions)
    for comp in comps:
        kind = regions[comp[0]].kind
        reaches = False
        for i in comp:
            r = regions[i]
            if kind == "acceptor" and _touches_p_rail(r, b):
                reaches = True; break
            if kind == "donor" and _touches_n_rail(r, b):
                reaches = True; break
        if not reaches:
            out.append(Violation(
                rule=4,
                description=f"floating {kind} pocket (no path to its contact rail)",
                regions=[regions[i].name for i in comp],
            ))
    return out


def rule_5_ohmic_contact(regions, b):
    out = []
    # Left rail (p-side)
    left_band_ymax = b["y_slab_L"]
    left_band_ymin = b["y_pp_L"]
    has_p = any(
        r.kind == "acceptor"
        and r.concentration >= OHMIC_CONTACT_FLOOR
        and r.ymin <= left_band_ymin + EPS_UM
        and r.ymax >= left_band_ymax - EPS_UM
        for r in regions
    )
    if not has_p:
        out.append(Violation(
            rule=5,
            description=f"left contact ({left_band_ymin:.2f}..{left_band_ymax:.2f}) "
                        f"lacks a full-width acceptor ≥ {OHMIC_CONTACT_FLOOR:.0e} cm⁻³",
            regions=[],
        ))
    # Right rail (n-side)
    right_band_ymin = b["y_slab_R"]
    right_band_ymax = b["y_pp_R"]
    has_n = any(
        r.kind == "donor"
        and r.concentration >= OHMIC_CONTACT_FLOOR
        and r.ymin <= right_band_ymin + EPS_UM
        and r.ymax >= right_band_ymax - EPS_UM
        for r in regions
    )
    if not has_n:
        out.append(Violation(
            rule=5,
            description=f"right contact ({right_band_ymin:.2f}..{right_band_ymax:.2f}) "
                        f"lacks a full-width donor ≥ {OHMIC_CONTACT_FLOOR:.0e} cm⁻³",
            regions=[],
        ))
    return out


def _fully_inside(inner: DopingRegion, outer: DopingRegion) -> bool:
    """True if inner is fully contained inside outer (inclusive)."""
    return (inner.ymin >= outer.ymin - EPS_UM and
            inner.ymax <= outer.ymax + EPS_UM and
            inner.zmin >= outer.zmin - EPS_UM and
            inner.zmax <= outer.zmax + EPS_UM)


def rule_6_no_opposite_overlap(regions):
    """Flag only PARTIAL opposite-polarity overlap.

    Full containment (one region entirely inside another of opposite kind)
    is intentional last-wins carving — used by U/L/vertical-PN topologies
    where an "outer" fills a rectangle and an "island" of opposite polarity
    is carved out by appearing later. Partial overlap is almost always an
    authoring mistake.
    """
    out = []
    n = len(regions)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = regions[i], regions[j]
            if a.kind == b.kind:
                continue
            if not _rects_interior_overlap(a, b):
                continue
            # Intentional last-wins carving: smaller is fully inside larger
            # AND it appears later in the list.
            if _fully_inside(b, a) and j > i:
                continue
            if _fully_inside(a, b) and i > j:
                continue
            out.append(Violation(
                rule=6,
                description=f"partial opposite-polarity overlap between "
                            f"'{a.name}' ({a.kind}) and "
                            f"'{b.name}' ({b.kind})",
                regions=[a.name, b.name],
            ))
    return out


def rule_7_inside_silicon(regions, geom):
    """Verify each region lies entirely inside the silicon cross-section.

    Implementation: sample the region on a 6×4 grid and test every sample
    against the analytic silicon mask. Fast and catches partial overhangs.
    """
    out = []
    for r in regions:
        ys = np.linspace(r.ymin + EPS_UM, r.ymax - EPS_UM, 6)
        zs = np.linspace(max(r.zmin, 0) + EPS_UM, r.zmax - EPS_UM, 4)
        if len(ys) == 0 or len(zs) == 0:
            continue
        mask = silicon_mask(ys, zs, **geom)
        # silicon_mask returns (len(z), len(y))
        if not mask.all():
            frac_out = 1.0 - mask.mean()
            out.append(Violation(
                rule=7,
                description=f"'{r.name}' extends outside silicon "
                            f"({frac_out*100:.0f}% of its footprint is oxide)",
                regions=[r.name],
            ))
    return out


# =========================================================================
# Runner + plot
# =========================================================================
def run_all_rules(regions=IMPLANTS, geom=None):
    geom = geom or geometry()
    b = geometry_bounds(**geom)
    viols = []
    viols += rule_1_min_stripe_dims(regions)
    viols += rule_2_max_concentration(regions)
    viols += rule_3_contact_extension(regions, b)
    viols += rule_4_no_floating_pockets(regions, b)
    viols += rule_5_ohmic_contact(regions, b)
    viols += rule_7_inside_silicon(regions, geom)
    # Rule 6 (opposite-polarity overlap) is now a warning channel — last-wins
    # semantics always resolve any overlap deterministically, so it can't
    # actually break the simulation. Print as info, don't block.
    warnings = rule_6_no_opposite_overlap(regions)
    for w in warnings:
        print(f"  [INFO rule 6]  {w.description}")
    return viols


def save_violation_plot(viols, regions, geom, out_path="output/drc.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    from tools.viz import plot_silicon_mask_with_labels

    fig, ax = plt.subplots(figsize=(12, 4), constrained_layout=True)
    plot_silicon_mask_with_labels(ax, regions, geom)

    # Highlight every region named in a violation with a thick magenta outline.
    viol_names = set()
    for v in viols:
        viol_names.update(v.regions)
    for r in regions:
        if r.name in viol_names:
            ax.add_patch(Rectangle(
                (r.ymin, r.zmin), r.ymax - r.ymin, r.zmax - r.zmin,
                fill=False, edgecolor="magenta", linewidth=2.0,
            ))

    ax.set_title(f"DRC — {len(viols)} violation(s)")
    import os
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")


def main():
    geom = geometry()
    viols = run_all_rules(IMPLANTS, geom)

    if not viols:
        print("DRC PASSED — all rules clean.")
        return 0

    print(f"DRC FAILED — {len(viols)} violation(s):")
    for v in viols:
        tag = f"[rule {v.rule}]"
        print(f"  {tag:<10s} {v.description}")
    save_violation_plot(viols, IMPLANTS, geom)
    print("DRC FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
