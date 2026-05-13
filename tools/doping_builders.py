"""Parametric doping-profile builders for the PN auto-design agent.

Each builder returns a list of `DopingRegion` boxes. The agent composes
these into `design.IMPLANTS`. Builders intentionally stay close to the
autoresearch hero builders (Yong 2017 campaign) so that U / L / V / graded
topologies port over cleanly once we're past the constant-doping baseline.

Convention:
- y is lateral (across the waveguide), z is vertical (substrate normal).
- Silicon sits in z in [0, h_core]; slab in z in [0, h_slab].
- The mode centre is at y = 0, z = h_core / 2.
- "Last-wins" merge semantics when regions overlap (matches Tidy3D's
  `GaussianDoping` step-function behaviour with `width=0.001`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class DopingRegion:
    """Axis-aligned rectangular doping stripe (cross-section, invariant in x)."""
    kind: Literal["acceptor", "donor"]
    concentration: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    name: str = ""

    @property
    def species(self) -> str:
        # Alias used by preview / DRC for legacy compatibility with the
        # autoresearch workflow.
        return self.kind

    @property
    def peak(self) -> float:
        return float(self.concentration)


# =========================================================================
# Geometry defaults
#
# The SISCAP constant-doping notebook uses:
#   h_core = 0.22, h_slab = 0.09, w_core = 0.50,
#   w_clearance = 2.0 (slab half-extent),
#   w_contact  = 1.0 (contact / side-pad width).
# We expose them as kwargs so higher layers can tune w_core for the agent.
# =========================================================================

def _default_geometry():
    return dict(h_core=0.22, h_slab=0.09, w_core=0.50,
                w_clearance=2.0, w_contact=1.0)


def geometry_bounds(h_core=0.22, h_slab=0.09, w_core=0.50,
                    w_clearance=2.0, w_contact=1.0):
    """Return the y-edge coordinates of the standard lateral layout.

    Layout (along y, symmetric about 0):

        |  p++  |  ...slab clearance...  |  core  |  ...slab clearance...  |  n++  |
        y_pp_L   y_slab_L              -w/2     +w/2              y_slab_R   y_pp_R
    """
    y_slab_L = -w_core / 2 - w_clearance
    y_slab_R = +w_core / 2 + w_clearance
    y_pp_L = y_slab_L - w_contact
    y_pp_R = y_slab_R + w_contact
    return dict(y_pp_L=y_pp_L, y_slab_L=y_slab_L,
                y_slab_R=y_slab_R, y_pp_R=y_pp_R,
                w_tot=y_pp_R - y_pp_L)


# =========================================================================
# build_lateral_pn — symmetric constant-doping baseline (SISCAP-style)
# =========================================================================

def build_lateral_pn(
    Np_core: float = 5e17, Nn_core: float = 3e17,
    Np_plus: float = 2e18, Nn_plus: float = 3e18,
    Np_pp: float = 1e20,  Nn_pp: float = 1e20,
    # junction position and intermediate-doping stripe widths (um)
    y_junction: float = 0.0,
    wp_plus: float = 0.12,   # p+ stripe width in the core-adjacent slab
    wn_plus: float = 0.14,   # n+ stripe width in the core-adjacent slab
    # geometry
    h_core: float = 0.22, h_slab: float = 0.09, w_core: float = 0.50,
    w_clearance: float = 2.0, w_contact: float = 1.0,
) -> list[DopingRegion]:
    """Canonical 6-stripe lateral PN. Matches the SISCAP notebook defaults.

    Returns an ordered list of `DopingRegion`s (last-wins on overlap).

    Stripes along y (left to right):

        p++  |  p+_slab  |  p_core  | n_core  |  n+_slab  |  n++
    """
    b = geometry_bounds(h_core=h_core, h_slab=h_slab, w_core=w_core,
                        w_clearance=w_clearance, w_contact=w_contact)
    y_pp_L, y_slab_L = b["y_pp_L"], b["y_slab_L"]
    y_slab_R, y_pp_R = b["y_slab_R"], b["y_pp_R"]

    # Intermediate-doping stripe edges (p+ sits just outside the core on the
    # slab; same for n+).
    y_p_plus_inner = -w_core / 2             # touches core edge
    y_p_plus_outer = y_p_plus_inner - wp_plus
    y_n_plus_inner = +w_core / 2
    y_n_plus_outer = y_n_plus_inner + wn_plus

    # Slab bottom extent — Tidy3D's step-function doping ignores z<0 anyway,
    # but we keep the explicit limit to match SISCAP (and to keep DRC sane).
    z_slab_bot = 0.0
    z_core_bot = 0.0

    regions: list[DopingRegion] = []

    # --- contacts (p++ / n++): from the outer edge of the slab to w_tot ---
    regions.append(DopingRegion(
        kind="acceptor", concentration=Np_pp,
        ymin=y_pp_L, ymax=y_slab_L,
        zmin=z_slab_bot, zmax=h_core,   # full-height so contacts have ohmic access
        name="p_pp",
    ))
    regions.append(DopingRegion(
        kind="donor", concentration=Nn_pp,
        ymin=y_slab_R, ymax=y_pp_R,
        zmin=z_slab_bot, zmax=h_core,
        name="n_pp",
    ))

    # --- p+ / n+ (slab-level intermediate doping between contacts and core) ---
    regions.append(DopingRegion(
        kind="acceptor", concentration=Np_plus,
        ymin=y_slab_L, ymax=y_p_plus_outer,
        zmin=z_slab_bot, zmax=h_slab,
        name="p_plus_slab",
    ))
    regions.append(DopingRegion(
        kind="donor", concentration=Nn_plus,
        ymin=y_n_plus_outer, ymax=y_slab_R,
        zmin=z_slab_bot, zmax=h_slab,
        name="n_plus_slab",
    ))

    # --- p+ / n+ ring immediately adjacent to the core on the slab ---
    regions.append(DopingRegion(
        kind="acceptor", concentration=Np_plus,
        ymin=y_p_plus_outer, ymax=y_p_plus_inner,
        zmin=z_slab_bot, zmax=h_slab,
        name="p_plus_edge",
    ))
    regions.append(DopingRegion(
        kind="donor", concentration=Nn_plus,
        ymin=y_n_plus_inner, ymax=y_n_plus_outer,
        zmin=z_slab_bot, zmax=h_slab,
        name="n_plus_edge",
    ))

    # --- p / n core: half-and-half across y_junction ---
    regions.append(DopingRegion(
        kind="acceptor", concentration=Np_core,
        ymin=-w_core / 2, ymax=y_junction,
        zmin=z_core_bot, zmax=h_core,
        name="p_core",
    ))
    regions.append(DopingRegion(
        kind="donor", concentration=Nn_core,
        ymin=y_junction, ymax=+w_core / 2,
        zmin=z_core_bot, zmax=h_core,
        name="n_core",
    ))

    return regions


# =========================================================================
# build_ushape_pn — Yong 2017-style U-junction
#
#   A rectangular "island" of one polarity sits inside the core, wrapped on
#   all sides by the opposite polarity ("outer"). A slab-level channel
#   connects the island to its matching contact rail so the 2D CHARGE
#   solver can inject current into the pocket.
#
#   Reference: Z. Yong et al., "U-shaped PN junctions for efficient silicon
#   Mach–Zehnder and microring modulators in the O-band," Opt. Express 25(7),
#   8425 (2017). DOI 10.1364/OE.25.008425.
# =========================================================================

def build_ushape_pn(
    island_width_um: float = 0.30,
    island_height_um: float = 0.080,
    island_position: Literal["top", "bottom", "center"] = "center",
    n_in_island: bool = False,         # island is P when False (Yong's geom)
    Np_core: float = 1e18, Nn_core: float = 1e18,
    Np_plus: float = 2e18, Nn_plus: float = 3e18,
    Np_pp: float = 1e20,   Nn_pp: float = 1e20,
    wp_plus: float = 0.12, wn_plus: float = 0.14,
    h_core: float = 0.22, h_slab: float = 0.09, w_core: float = 0.50,
    w_clearance: float = 2.0, w_contact: float = 1.0,
) -> list[DopingRegion]:
    """U-shape: island of one type inside, outer of opposite type wrapping.

    island_position picks the vertical placement of the island. Use
    `n_in_island=False` (default) for Yong's geometry — P pocket in an N
    outer.
    """
    island_width_um = min(island_width_um, 0.95 * w_core)
    island_height_um = min(island_height_um, 0.95 * h_core)

    y_isl_min = -island_width_um / 2
    y_isl_max = +island_width_um / 2
    if island_position == "top":
        z_isl_min = h_core - island_height_um
        z_isl_max = h_core
    elif island_position == "bottom":
        z_isl_min = 0.0
        z_isl_max = island_height_um
    elif island_position == "center":
        z_isl_min = (h_core - island_height_um) / 2
        z_isl_max = z_isl_min + island_height_um
    else:
        raise ValueError(f"unknown island_position={island_position!r}")

    outer_kind  = "donor" if n_in_island else "acceptor"  # wrong — outer is opposite
    # Actually: if island is N (n_in_island=True), outer is P → acceptor.
    # If island is P (n_in_island=False), outer is N → donor.
    outer_kind  = "acceptor" if n_in_island else "donor"
    island_kind = "donor" if n_in_island else "acceptor"
    outer_conc  = Np_core if outer_kind == "acceptor" else Nn_core
    island_conc = Np_core if island_kind == "acceptor" else Nn_core

    # Start from the standard ladder (p++/p+/n+/n++ stripes), then REPLACE
    # the p_core + n_core pair with a single outer region spanning the whole
    # core. The island is appended last (last-wins semantics carve it out).
    base = build_lateral_pn(
        Np_core=Np_core, Nn_core=Nn_core,
        Np_plus=Np_plus, Nn_plus=Nn_plus,
        Np_pp=Np_pp, Nn_pp=Nn_pp,
        y_junction=0.0, wp_plus=wp_plus, wn_plus=wn_plus,
        h_core=h_core, h_slab=h_slab, w_core=w_core,
        w_clearance=w_clearance, w_contact=w_contact,
    )
    regions = [r for r in base if r.name not in ("p_core", "n_core")]

    # Outer: whole core filled with the opposite polarity to the island.
    regions.append(DopingRegion(
        kind=outer_kind, concentration=outer_conc,
        ymin=-w_core / 2, ymax=+w_core / 2,
        zmin=0.0, zmax=h_core,
        name="u_outer",
    ))

    # Island (last-wins carves it out of the outer).
    regions.append(DopingRegion(
        kind=island_kind, concentration=island_conc,
        ymin=y_isl_min, ymax=y_isl_max,
        zmin=z_isl_min, zmax=z_isl_max,
        name="u_island",
    ))

    # Slab-level channel carves a bridge through u_outer's slab region so
    # the island connects to its matching contact rail. (Yong's fix — in
    # a 2D CHARGE sim a disconnected island makes the solver diverge.)
    #
    # The channel only needs to cover the slab *within* u_outer between
    # the island edge and the core edge. The existing p_plus_edge /
    # p_plus_slab ladder already provides the P-path outside the core, so
    # we don't need to extend all the way to the contact rail (doing so
    # would over-subtract from the p+ stripes via merge_overlapping_regions).
    if island_kind == "donor":
        # N island → carve toward N rail through the right half of u_outer
        ch_ymin = max(0.0, y_isl_max - 0.02)
        ch_ymax = w_core / 2
        wall_y = w_core / 2 - 0.03       # right wall of core
    else:
        # P island → carve toward P rail through the left half of u_outer
        ch_ymin = -w_core / 2
        ch_ymax = min(0.0, y_isl_min + 0.02)
        wall_y = -w_core / 2 + 0.03      # left wall of core
    regions.append(DopingRegion(
        kind=island_kind, concentration=island_conc,
        ymin=ch_ymin, ymax=ch_ymax,
        zmin=0.0, zmax=h_slab,
        name="u_channel_to_contact",
    ))
    # If island bottom is above the slab (top-position), the slab-level
    # channel can't directly touch the island. Add a horizontal "ceiling"
    # strip at the island's matching side that connects channel-top to
    # island-bottom. Strip is on the island's matching-polarity side,
    # spanning from the core wall to just past the island edge.
    if z_isl_min > h_slab + 1e-9:
        bridge_z_min = max(0.0, h_slab - 0.005)
        bridge_z_max = z_isl_min + 0.002
        if island_kind == "donor":
            # N bridge on the right: from core wall to past island right edge
            bridge_ymin = y_isl_max - 0.020
            bridge_ymax = +w_core / 2
        else:
            # P bridge on the left: from core wall to past island left edge
            bridge_ymin = -w_core / 2
            bridge_ymax = y_isl_min + 0.020
        regions.append(DopingRegion(
            kind=island_kind, concentration=island_conc,
            ymin=bridge_ymin, ymax=bridge_ymax,
            zmin=bridge_z_min, zmax=bridge_z_max,
            name="u_z_bridge",
        ))
    return regions


# =========================================================================
# build_lshape_pn — a single corner of opposite polarity inside the core
#
#   One polarity fills a rectangular corner of the core; the other fills
#   the rest. Only two junctions (one vertical, one horizontal) meet at
#   the corner, and they sit under the mode peak. Matches Zhou 2018 and
#   is a lighter-weight alternative to the U-shape (fewer junctions →
#   less C) while still breaking the constant-doping tradeoff.
# =========================================================================

def build_lshape_pn(
    corner: Literal["bl", "br", "tl", "tr"] = "bl",
    corner_width_um: float = 0.15,
    corner_height_um: float = 0.080,
    corner_type: Literal["p", "n"] = "p",
    Np_core: float = 1e18, Nn_core: float = 1e18,
    Np_plus: float = 2e18, Nn_plus: float = 3e18,
    Np_pp: float = 1e20,   Nn_pp: float = 1e20,
    wp_plus: float = 0.12, wn_plus: float = 0.14,
    h_core: float = 0.22, h_slab: float = 0.09, w_core: float = 0.50,
    w_clearance: float = 2.0, w_contact: float = 1.0,
) -> list[DopingRegion]:
    """L-shape: one corner of opposite polarity inside an otherwise uniform core.

    `corner` in {bl, br, tl, tr} picks which corner of the rib the corner
    region occupies. `corner_type` is "p" or "n" — the corner's polarity.
    """
    cw = min(corner_width_um, 0.95 * w_core)
    ch = min(corner_height_um, 0.95 * h_core)

    if corner == "bl":
        c_ymin, c_ymax = -w_core / 2, -w_core / 2 + cw
        c_zmin, c_zmax = 0.0, ch
    elif corner == "br":
        c_ymin, c_ymax = +w_core / 2 - cw, +w_core / 2
        c_zmin, c_zmax = 0.0, ch
    elif corner == "tl":
        c_ymin, c_ymax = -w_core / 2, -w_core / 2 + cw
        c_zmin, c_zmax = h_core - ch, h_core
    elif corner == "tr":
        c_ymin, c_ymax = +w_core / 2 - cw, +w_core / 2
        c_zmin, c_zmax = h_core - ch, h_core
    else:
        raise ValueError(f"unknown corner={corner!r}")

    outer_kind = "donor" if corner_type == "p" else "acceptor"
    corner_kind = "acceptor" if corner_type == "p" else "donor"
    outer_conc  = Np_core if outer_kind == "acceptor" else Nn_core
    corner_conc = Np_core if corner_kind == "acceptor" else Nn_core

    base = build_lateral_pn(
        Np_core=Np_core, Nn_core=Nn_core,
        Np_plus=Np_plus, Nn_plus=Nn_plus, Np_pp=Np_pp, Nn_pp=Nn_pp,
        y_junction=0.0, wp_plus=wp_plus, wn_plus=wn_plus,
        h_core=h_core, h_slab=h_slab, w_core=w_core,
        w_clearance=w_clearance, w_contact=w_contact,
    )
    regions = [r for r in base if r.name not in ("p_core", "n_core")]
    # Background: whole core filled with the "outer" polarity
    regions.append(DopingRegion(
        kind=outer_kind, concentration=outer_conc,
        ymin=-w_core / 2, ymax=+w_core / 2,
        zmin=0.0, zmax=h_core, name="l_background",
    ))
    # Corner: overrides background in its footprint via last-wins.
    regions.append(DopingRegion(
        kind=corner_kind, concentration=corner_conc,
        ymin=c_ymin, ymax=c_ymax,
        zmin=c_zmin, zmax=c_zmax, name="l_corner",
    ))
    return regions


# =========================================================================
# build_zshape_pn — zigzag PN junction
#
#   The P-N boundary makes a Z (horizontal step at mid-height) so the
#   junction line passes through the mode peak via one extra horizontal
#   edge. More junction perimeter per unit length than a simple lateral
#   junction, but less than a U-shape (one zig, not a full island).
#   Variant "ZPN" in Patel OFC'26 review.
# =========================================================================

def build_zshape_pn(
    y_top_um: float = -0.05,        # P-N boundary y-position in top half
    y_bot_um: float = +0.05,        # P-N boundary y-position in bottom half
    z_step_um: float | None = None, # height of horizontal step (default: h_core/2)
    Np_core: float = 1e18, Nn_core: float = 1e18,
    Np_plus: float = 2e18, Nn_plus: float = 3e18,
    Np_pp: float = 1e20,   Nn_pp: float = 1e20,
    wp_plus: float = 0.12, wn_plus: float = 0.14,
    h_core: float = 0.22, h_slab: float = 0.09, w_core: float = 0.50,
    w_clearance: float = 2.0, w_contact: float = 1.0,
) -> list[DopingRegion]:
    """Z-shape (zigzag) PN junction.

    Top half: P fills y < y_top, N fills y > y_top.
    Bottom half: P fills y < y_bot, N fills y > y_bot.
    With y_top < y_bot, the PN boundary makes a "Z" stepping rightward
    at the horizontal break z=z_step. The step passes under the mode
    peak and adds (y_bot - y_top) of extra junction perimeter.
    """
    z_step = z_step_um if z_step_um is not None else h_core / 2

    # Constrain the junctions to inside the core
    y_top = max(-w_core / 2 + 0.001, min(w_core / 2 - 0.001, y_top_um))
    y_bot = max(-w_core / 2 + 0.001, min(w_core / 2 - 0.001, y_bot_um))

    base = build_lateral_pn(
        Np_core=Np_core, Nn_core=Nn_core,
        Np_plus=Np_plus, Nn_plus=Nn_plus, Np_pp=Np_pp, Nn_pp=Nn_pp,
        y_junction=0.0, wp_plus=wp_plus, wn_plus=wn_plus,
        h_core=h_core, h_slab=h_slab, w_core=w_core,
        w_clearance=w_clearance, w_contact=w_contact,
    )
    regions = [r for r in base if r.name not in ("p_core", "n_core")]

    # Top half
    regions.append(DopingRegion(
        kind="acceptor", concentration=Np_core,
        ymin=-w_core / 2, ymax=y_top,
        zmin=z_step, zmax=h_core, name="z_p_top",
    ))
    regions.append(DopingRegion(
        kind="donor", concentration=Nn_core,
        ymin=y_top, ymax=+w_core / 2,
        zmin=z_step, zmax=h_core, name="z_n_top",
    ))
    # Bottom half
    regions.append(DopingRegion(
        kind="acceptor", concentration=Np_core,
        ymin=-w_core / 2, ymax=y_bot,
        zmin=0.0, zmax=z_step, name="z_p_bot",
    ))
    regions.append(DopingRegion(
        kind="donor", concentration=Nn_core,
        ymin=y_bot, ymax=+w_core / 2,
        zmin=0.0, zmax=z_step, name="z_n_bot",
    ))
    return regions


# =========================================================================
# build_graded_pn — stepped concentration profile approximating a smooth gradient
#
#   Breaks the core into `n_steps` vertical stripes of alternating P/N
#   density following a user-provided concentration schedule. Useful for
#   probing "soft" junctions (wide depletion at intermediate densities)
#   and PIN-style designs (set one or more inner steps to ~1e15 for
#   near-intrinsic).
# =========================================================================

def build_graded_pn(
    p_concentrations: list[float],   # Acceptor density per stripe, left→right
    n_concentrations: list[float],   # Donor density per stripe, left→right
    # len(p_concentrations) + len(n_concentrations) = number of stripes;
    # all P stripes come before the 0-junction, all N stripes after.
    Np_plus: float = 2e18, Nn_plus: float = 3e18,
    Np_pp: float = 1e20,   Nn_pp: float = 1e20,
    wp_plus: float = 0.12, wn_plus: float = 0.14,
    h_core: float = 0.22, h_slab: float = 0.09, w_core: float = 0.50,
    w_clearance: float = 2.0, w_contact: float = 1.0,
) -> list[DopingRegion]:
    """Stepped graded PN: p-core side split into len(p_concentrations)
    vertical stripes of decreasing concentration toward the junction,
    n-core side symmetric. Set small internal values (~1e15) to get a
    PIN-like near-intrinsic band across the mode peak.
    """
    base = build_lateral_pn(
        Np_plus=Np_plus, Nn_plus=Nn_plus, Np_pp=Np_pp, Nn_pp=Nn_pp,
        y_junction=0.0, wp_plus=wp_plus, wn_plus=wn_plus,
        h_core=h_core, h_slab=h_slab, w_core=w_core,
        w_clearance=w_clearance, w_contact=w_contact,
    )
    regions = [r for r in base if r.name not in ("p_core", "n_core")]

    # Split the P half of the core (y: -w_core/2 to 0) into n_p stripes,
    # decreasing concentration from left (heaviest) to right (lightest).
    n_p = len(p_concentrations)
    n_n = len(n_concentrations)
    if n_p == 0 or n_n == 0:
        raise ValueError("Need at least 1 P stripe and 1 N stripe.")

    p_edges = [-w_core / 2 + k * (w_core / 2) / n_p for k in range(n_p + 1)]
    for k in range(n_p):
        regions.append(DopingRegion(
            kind="acceptor", concentration=float(p_concentrations[k]),
            ymin=p_edges[k], ymax=p_edges[k + 1],
            zmin=0.0, zmax=h_core,
            name=f"p_grad_{k}",
        ))
    n_edges = [k * (w_core / 2) / n_n for k in range(n_n + 1)]
    for k in range(n_n):
        regions.append(DopingRegion(
            kind="donor", concentration=float(n_concentrations[k]),
            ymin=n_edges[k], ymax=n_edges[k + 1],
            zmin=0.0, zmax=h_core,
            name=f"n_grad_{k}",
        ))
    return regions


# =========================================================================
# merge_overlapping_regions — resolve overlaps via last-wins carving
#
# Tidy3D's `GaussianDoping` boxes are additive in Nd and Na. If two boxes
# of opposite polarity overlap, the solver sees Nd > 0 AND Na > 0 at the
# overlap, which compensates to ~intrinsic — NOT the "inner carves out
# outer" semantics used by U/L/vertical-PN topologies.
#
# This function rewrites the IMPLANTS list so that every (y, z) point
# belongs to at most one region. Last-wins: a later region removes its
# footprint from every earlier region (regardless of polarity). The
# result is an ordered list of non-overlapping axis-aligned rectangles,
# semantically identical to the original under last-wins, and safe to
# hand directly to Tidy3D.
# =========================================================================

def _subtract_rect(A, B, eps=1e-9):
    """Return list of axis-aligned rectangles representing A \\ B.

    Each rectangle is the 4-tuple (ymin, ymax, zmin, zmax). Produces at
    most 4 sub-rectangles (the frame around the overlap).
    """
    ay1, ay2, az1, az2 = A
    by1, by2, bz1, bz2 = B
    oy1, oy2 = max(ay1, by1), min(ay2, by2)
    oz1, oz2 = max(az1, bz1), min(az2, bz2)
    # No real overlap?
    if oy1 >= oy2 - eps or oz1 >= oz2 - eps:
        return [A]
    parts = []
    # Bottom strip (below overlap)
    if az1 < oz1 - eps:
        parts.append((ay1, ay2, az1, oz1))
    # Top strip (above overlap)
    if oz2 < az2 - eps:
        parts.append((ay1, ay2, oz2, az2))
    # Left strip (within overlap z-band)
    if ay1 < oy1 - eps:
        parts.append((ay1, oy1, oz1, oz2))
    # Right strip
    if oy2 < ay2 - eps:
        parts.append((oy2, ay2, oz1, oz2))
    return parts


def _subtract_many(A, Bs, eps=1e-9):
    out = [A]
    for B in Bs:
        nxt = []
        for a in out:
            nxt.extend(_subtract_rect(a, B, eps=eps))
        out = nxt
    return out


def merge_overlapping_regions(regions, eps=1e-9):
    """Rewrite `regions` so the final list has zero overlaps, preserving
    the last-wins interpretation of the original.

    Implementation: each region's footprint is subtracted by every LATER
    region's footprint (regardless of polarity) — so later regions
    overwrite earlier ones, but within each region's remaining footprint
    the polarity/concentration is unchanged.
    """
    out: list[DopingRegion] = []
    for i, r in enumerate(regions):
        A = (r.ymin, r.ymax, r.zmin, r.zmax)
        Bs = [(rj.ymin, rj.ymax, rj.zmin, rj.zmax) for rj in regions[i + 1:]]
        parts = _subtract_many(A, Bs, eps=eps)
        for k, (y1, y2, z1, z2) in enumerate(parts):
            if (y2 - y1) < eps or (z2 - z1) < eps:
                continue
            out.append(DopingRegion(
                kind=r.kind, concentration=r.concentration,
                ymin=y1, ymax=y2, zmin=z1, zmax=z2,
                name=f"{r.name}_p{k}" if len(parts) > 1 else r.name,
            ))
    return out


# =========================================================================
# Lightweight 2D rendering of IMPLANTS onto a (y, z) grid for preview / DRC
# =========================================================================

def render_net_doping(regions: list[DopingRegion],
                      y_grid, z_grid):
    """Return (Na, Nd, net) arrays of shape (len(z), len(y)).

    Uses *last-wins* semantics: later regions overwrite earlier ones in their
    footprint. This matches both the autoresearch renderer and the behaviour
    of stacked `GaussianDoping(width=0.001)` boxes in Tidy3D.
    """
    import numpy as np
    yy, zz = np.meshgrid(y_grid, z_grid, indexing="xy")
    Na = np.zeros_like(yy)
    Nd = np.zeros_like(yy)
    for r in regions:
        mask = (
            (yy >= r.ymin) & (yy <= r.ymax) &
            (zz >= r.zmin) & (zz <= r.zmax)
        )
        if not mask.any():
            continue
        if r.kind == "acceptor":
            Na[mask] = r.concentration
            Nd[mask] = 0.0
        else:
            Nd[mask] = r.concentration
            Na[mask] = 0.0
    net = Nd - Na
    return Na, Nd, net


def silicon_mask(y_grid, z_grid,
                 h_core=0.22, h_slab=0.09, w_core=0.50,
                 w_clearance=2.0, w_contact=1.0):
    """Boolean mask marking where silicon exists in the cross-section."""
    import numpy as np
    b = geometry_bounds(h_core=h_core, h_slab=h_slab, w_core=w_core,
                        w_clearance=w_clearance, w_contact=w_contact)
    yy, zz = np.meshgrid(y_grid, z_grid, indexing="xy")
    m = np.zeros_like(yy, dtype=bool)

    # core (rib): |y| <= w/2, 0 <= z <= h_core
    m |= (np.abs(yy) <= w_core / 2) & (zz >= 0) & (zz <= h_core)
    # slab: b.y_slab_L <= y <= b.y_slab_R, 0 <= z <= h_slab
    m |= (yy >= b["y_slab_L"]) & (yy <= b["y_slab_R"]) & (zz >= 0) & (zz <= h_slab)
    # contact-region silicon (full thickness for ohmic contact): between
    # y_pp and y_slab on each side, 0 <= z <= h_core
    m |= (yy >= b["y_pp_L"]) & (yy <= b["y_slab_L"]) & (zz >= 0) & (zz <= h_core)
    m |= (yy >= b["y_slab_R"]) & (yy <= b["y_pp_R"]) & (zz >= 0) & (zz <= h_core)
    return m
