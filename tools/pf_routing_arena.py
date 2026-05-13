"""
pf_routing_arena.py — PhotonForge integration for the Routing Arena algorithms.

Bridges between PhotonForge layout (continuous um coordinates) and the
grid-based routing algorithms in routing_algorithms.py (9 routers).

Usage:
    from pf_routing_arena import PFRoutingArena
    from routing_algorithms import HybridRipUpBundle

    arena = PFRoutingArena(
        bbox_min=(-200, -200), bbox_max=(800, 800),
        grid_pitch=25, router_class=HybridRipUpBundle,
    )
    arena.add_obstacles_from_layer(component, M2_layer, margin=1)
    arena.add_terminal_pair("D0", terminal1, terminal2)
    results = arena.route_all(trace_width=25, layer=M2_layer)
"""

from __future__ import annotations

import sys
import os
from dataclasses import dataclass, field

import photonforge as pf

# Import shared utilities from the Bundle_router integration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Bundle_router'))
from pf_maze_router import (
    GridMapping, compute_grid_mapping, rasterize_bbox,
    rasterize_structures, simplify_grid_path, smooth_corners,
    grid_path_to_layout_waypoints, TerminalPair, PFRouteResult,
)

from routing_algorithms import (
    Grid, BaseRouter, RouterResult,
    SequentialBFS, AStarRouter, BundleRouter,
    RiverRouter, NegotiationRouter, RipUpRouter,
    SmoothBundleRouter, HybridRipUpBundle, CorridorRouter,
    compare_routers,
)


# ── helper: trim a grid centerline so it starts/ends at the terminal edge ──
def _clip_path_to_terminal_edges(path, gm, terminal1, terminal2, min_cells=4):
    """
    Clip only the LARGE terminal ends. A terminal is considered large if
    its bbox covers at least `min_cells` grid cells — typically the 100um
    bondpad at the source side. Small terminals (like ~25um AMZI TPS pads)
    are left intact so the route reliably lands on them.

    For the large end we stop one cell inside the bbox (so the trace
    polygon still abuts the pad at the border), keeping the pad body
    visually distinct from the trace.
    """
    def _bbox_of(term):
        (x1, y1), (x2, y2) = term.bounds()
        r_tl, c_tl = gm.layout_to_grid(x1, y2)
        r_br, c_br = gm.layout_to_grid(x2, y1)
        r_min, r_max = min(r_tl, r_br), max(r_tl, r_br)
        c_min, c_max = min(c_tl, c_br), max(c_tl, c_br)
        return (r_min, r_max, c_min, c_max)

    def _in_bbox(cell, bb):
        r, c = cell; r_min, r_max, c_min, c_max = bb
        return r_min <= r <= r_max and c_min <= c <= c_max

    def _bbox_cell_count(bb):
        return (bb[1] - bb[0] + 1) * (bb[3] - bb[2] + 1)

    bb1 = _bbox_of(terminal1)
    bb2 = _bbox_of(terminal2)

    start_i = 0
    if _bbox_cell_count(bb1) >= min_cells:
        # Large terminal (bondpad): clip to edge
        for i, cell in enumerate(path):
            if not _in_bbox(cell, bb1):
                start_i = i
                break
        if start_i > 0:
            start_i -= 1   # keep one cell on the pad border

    end_i = len(path) - 1
    if _bbox_cell_count(bb2) >= min_cells:
        for i in range(len(path) - 1, -1, -1):
            if not _in_bbox(path[i], bb2):
                end_i = i
                break
        if end_i < len(path) - 1:
            end_i += 1     # keep one cell on the pad border

    if end_i < start_i + 1:
        return path
    return path[start_i:end_i + 1]


# ── Collision visualization (PhotonForge LVS pattern) ─────────────────
# GDS (99, 0) is unused by the PDK; safe to repurpose as annotation only.
# Following the pattern from PhotonForge's LVS guide — use pf.boolean on
# references' structures rather than flattening, and register a styled
# COLLISION layer so overlaps render as orangered cross-hatch.

def add_collision_layer(technology, layer_name="COLLISION",
                         layer_id=(99, 0), color="#ff4500cc", pattern="xx"):
    """Register a COLLISION annotation layer if not already present."""
    if layer_name in technology.layers:
        return
    technology.add_layer(layer_name, pf.LayerSpec(
        layer=layer_id,
        description="Geometry overlap / DRC collision highlight",
        color=color,
        pattern=pattern,
    ))


def show_collisions(component, layer, collision_layer="COLLISION"):
    """
    Return a visualization component with all pairwise geometry overlaps
    on `layer` highlighted on `collision_layer`.

    Checks:
      - top-level structures in `component` vs each reference on `layer`
      - every pair of references on `layer`

    Returns (vis_component, n_collision_regions).
    """
    result = pf.Component(f"{component.name} [collision map]")
    result.add_reference(component)

    try:
        main = component.get_structures(layer, depth=0)
    except Exception:
        main = []
    refs = list(component.references)
    n = 0

    def _label(ref):
        try:
            nm = ref.component.name if hasattr(ref, "component") else "?"
        except Exception:
            nm = "?"
        parts = nm.split("_")
        short = ("_".join(parts[:-1]) + "_…") if len(parts) > 1 else nm
        try:
            c = ref.center()
            return f"{short} @ ({c[0]:.0f}, {c[1]:.0f})"
        except Exception:
            return short

    for i, r0 in enumerate(refs):
        try:
            s0 = r0.get_structures(layer)
        except Exception:
            continue
        if main and s0:
            try:
                isect = pf.boolean(main, s0, "*")
            except Exception:
                isect = []
            if isect:
                result.add(collision_layer, *isect)
                n += len(isect)
                print(f"  COLLISION: main \u2194 {_label(r0)} — {len(isect)} region(s)")
        for j in range(i + 1, len(refs)):
            r1 = refs[j]
            try:
                s1 = r1.get_structures(layer)
            except Exception:
                continue
            if not s1:
                continue
            try:
                isect = pf.boolean(s0, s1, "*")
            except Exception:
                isect = []
            if isect:
                result.add(collision_layer, *isect)
                n += len(isect)
                print(f"  COLLISION: {_label(r0)} \u2194 {_label(r1)} — {len(isect)} region(s)")

    if n == 0:
        print(f"  No collisions on layer {layer!r}")
    return result, n


def show_route_violations(
    component,
    m2_layer=(12, 0),
    m1_layer=(11, 0),
    route_prefix="route_",
    collision_layer="COLLISION",
):
    """
    REAL routing DRC violations, excluding legitimate contact zones.

    Distinguishes:
      - route references (component name startswith route_prefix) = trace M2
      - baseline references (all others)                           = pad M2

    Legitimate contact = M1 overlapping BASELINE M2 pads (intended heater-to-pad electrical contact).
    Forbidden M1 zone  = M1 OUTSIDE any baseline M2 pad (the heater resistor body).

    Reports two kinds of violations:
      (a) Route trace polygon × forbidden-M1 zone (heater crossing = heatsink)
      (b) Route trace polygon × OTHER baseline M2 pads (crossing another net's contact)
          or route trace × other route trace (shorting different nets)

    Returns (vis_component, n_regions).
    """
    # Explicitly carry over the technology so COLLISION layer resolves correctly
    tech_obj = getattr(component, "technology", None) or pf.config.default_technology
    result = pf.Component(f"{component.name} [route violations]", technology=tech_obj)
    result.add_reference(component)

    all_refs = list(component.references)
    print(f"  show_route_violations: component={component.name!r}, total refs={len(all_refs)}")
    # Partition references
    route_refs = []
    baseline_refs = []
    for ref in all_refs:
        try:
            name = ref.component.name
        except Exception:
            name = ""
        if name.startswith(route_prefix):
            route_refs.append(ref)
        else:
            baseline_refs.append(ref)
    print(f"  partitioned: {len(route_refs)} route refs, {len(baseline_refs)} baseline refs")

    # Gather M2/M1 polygons per group
    def _get_strs(refs, layer):
        out = []
        for r in refs:
            try:
                out.extend(r.get_structures(layer))
            except Exception:
                pass
        return out

    baseline_m2 = _get_strs(baseline_refs, m2_layer)
    try:
        top_m2 = component.get_structures(m2_layer, depth=0)
    except Exception:
        top_m2 = []
    baseline_m2 = baseline_m2 + list(top_m2)
    all_m1 = _get_strs(baseline_refs + route_refs, m1_layer)
    try:
        top_m1 = component.get_structures(m1_layer, depth=0)
    except Exception:
        top_m1 = []
    all_m1 = all_m1 + list(top_m1)

    def _safe(a, b, op):
        try: return pf.boolean(a, b, op)
        except Exception: return []

    # Legitimate contact zone = M1 under baseline M2 (NOT under trace M2)
    m1_under_baseline = _safe(all_m1, baseline_m2, "*")
    m1_forbidden = _safe(all_m1, m1_under_baseline, "-") if m1_under_baseline else all_m1

    n_heater = 0
    n_otherpad = 0
    n_routeroute = 0

    # (a) Each route × forbidden M1
    for r in route_refs:
        route_m2 = _safe(r.get_structures(m2_layer), [], "+")
        if not route_m2: continue
        inter = _safe(route_m2, m1_forbidden, "*")
        for p in inter:
            result.add(collision_layer, p)
            n_heater += 1
        if inter:
            try:
                name = r.component.name
                print(f"  HEATER CROSS: {name} — {len(inter)} region(s)")
            except Exception:
                pass

    # (b) Each route × OTHER baseline M2 pads
    # But we need to know "other" vs "own target pad" — skip this for now
    # and check route × route (which is unambiguous).
    for i, r0 in enumerate(route_refs):
        s0 = r0.get_structures(m2_layer)
        if not s0: continue
        for j in range(i + 1, len(route_refs)):
            r1 = route_refs[j]
            s1 = r1.get_structures(m2_layer)
            if not s1: continue
            inter = _safe(s0, s1, "*")
            for p in inter:
                result.add(collision_layer, p)
                n_routeroute += 1
            if inter:
                try:
                    na, nb = r0.component.name, r1.component.name
                    print(f"  ROUTE×ROUTE: {na} ↔ {nb} — {len(inter)} region(s)")
                except Exception:
                    pass

    # (c) Pad × Pad (baseline × baseline M2 overlap) — only among bondpad-like
    # references (small baseline refs). This catches adjacent pad overlap.
    # Use top-level bondpad references (which are what we added via
    # projector_circuit.add(pf.Reference(bp))).
    for i, r0 in enumerate(baseline_refs):
        try:
            nm0 = r0.component.name
        except Exception:
            continue
        if "BondPad" not in nm0:
            continue
        s0 = r0.get_structures(m2_layer)
        if not s0: continue
        for j in range(i + 1, len(baseline_refs)):
            r1 = baseline_refs[j]
            try:
                nm1 = r1.component.name
            except Exception:
                continue
            if "BondPad" not in nm1:
                continue
            s1 = r1.get_structures(m2_layer)
            if not s1: continue
            inter = _safe(s0, s1, "*")
            for p in inter:
                result.add(collision_layer, p)
                n_otherpad += 1

    print(f"  Summary: heater_cross={n_heater}, route_x_route={n_routeroute}, pad_x_pad={n_otherpad}")
    return result, (n_heater + n_routeroute + n_otherpad)


# Name → class lookup for convenience
ROUTERS = {
    "BFS": SequentialBFS,
    "A*": AStarRouter,
    "Bundle": BundleRouter,
    "River": RiverRouter,
    "Negotiation": NegotiationRouter,
    "Rip-Up": RipUpRouter,
    "Smooth Bundle": SmoothBundleRouter,
    "Hybrid": HybridRipUpBundle,
    "Corridor": CorridorRouter,
}


class PFRoutingArena:
    """
    PhotonForge integration for the Routing Arena algorithms.

    Wraps any BaseRouter subclass with:
    - Layout geometry → grid obstacle rasterization
    - Terminal positions → grid coordinate mapping
    - Grid paths → PF Path components
    - Pad reservation for multi-pad layouts
    """

    def __init__(
        self,
        bbox_min: tuple[float, float],
        bbox_max: tuple[float, float],
        grid_pitch: float,
        margin: int = 5,
        router_class: type = HybridRipUpBundle,
        **router_kwargs,
    ):
        self.gm = compute_grid_mapping(bbox_min, bbox_max, grid_pitch, margin)
        self.grid = Grid(self.gm.rows, self.gm.cols)
        self.router_class = router_class
        self.router_kwargs = router_kwargs
        self.terminal_pairs: list[TerminalPair] = []
        self.results: list[PFRouteResult] = []

    @property
    def grid_pitch(self) -> float:
        return self.gm.grid_pitch

    # ── Obstacle management ──────────────────────────────────────

    def add_obstacles_from_layer(
        self,
        component: pf.Component,
        layer,
        margin: int = 0,
        inflate_um: float = 0.0,
    ):
        """Rasterize all structures on a layer as grid obstacles.

        If inflate_um > 0, the polygons are INFLATED in layout coords by
        that amount before rasterization. Use inflate_um = trace_width/2
        + epsilon to guarantee every grid cell whose trace polygon could
        touch the obstacle gets blocked.
        """
        if inflate_um > 0:
            from pf_maze_router import rasterize_structures_inflated
            cells = rasterize_structures_inflated(self.gm, component, layer, inflate_um)
        else:
            cells = rasterize_structures(self.gm, component, layer, margin)
        for r, c in cells:
            self.grid.add_obstacle(r, c)

    def add_obstacle_rect(
        self,
        x_min: float, y_min: float,
        x_max: float, y_max: float,
        margin: int = 0,
    ):
        """Add a rectangular obstacle in layout coordinates."""
        cells = rasterize_bbox(self.gm, x_min, y_min, x_max, y_max, margin)
        for r, c in cells:
            self.grid.add_obstacle(r, c)

    # ── Terminal pairs ───────────────────────────────────────────

    def add_terminal_pair(
        self,
        name: str,
        terminal1: pf.Terminal,
        terminal2: pf.Terminal,
        source_dir: str | None = None,
        target_dir: str | None = None,
    ):
        """Register a terminal pair. Optional direction constraints (N/S/E/W)."""
        tp = TerminalPair(name, terminal1, terminal2)
        tp.source_dir = source_dir
        tp.target_dir = target_dir
        self.terminal_pairs.append(tp)

    # ── Footprint helpers ────────────────────────────────────────

    def _get_terminal_footprint(self, terminal: pf.Terminal, margin: int = 0):
        bb_min, bb_max = terminal.bounds()
        return rasterize_bbox(
            self.gm, bb_min[0], bb_min[1], bb_max[0], bb_max[1], margin=margin,
        )

    # ── Main routing entry point ─────────────────────────────────

    def route_all(
        self,
        trace_width: float,
        layer=None,
    ) -> list[PFRouteResult]:
        """
        Route all terminal pairs by handing ALL nets to the selected router
        in a single call. This preserves the multi-net behavior of
        Negotiation / Rip-Up / Hybrid / River algorithms — previously nullified
        by per-net invocation.

        Each net carries a "footprint" field: its pad exit-zone cells. The
        router's _reserve_pins / _prepare_blocked treat other nets' footprints
        as obstacles but open the current net's own footprint when routing it.
        """
        # Build all_nets with per-net footprints
        all_nets = []
        for tp in self.terminal_pairs:
            c1 = tp.terminal1.center()
            c2 = tp.terminal2.center()
            src = self.gm.layout_to_grid(c1[0], c1[1])
            tgt = self.gm.layout_to_grid(c2[0], c2[1])
            exit1 = set(self._get_terminal_footprint(tp.terminal1, margin=1))
            exit2 = set(self._get_terminal_footprint(tp.terminal2, margin=1))
            net_def = {
                "name": tp.name,
                "source": src,
                "target": tgt,
                "footprint": exit1 | exit2,
            }
            if hasattr(tp, 'source_dir') and tp.source_dir:
                net_def["source_dir"] = tp.source_dir
            if hasattr(tp, 'target_dir') and tp.target_dir:
                net_def["target_dir"] = tp.target_dir
            all_nets.append(net_def)

        # Mark ALL pad footprints as obstacles. The router will discard
        # the current net's own footprint when preparing blocked sets.
        for net_def in all_nets:
            for cell in net_def["footprint"]:
                self.grid.add_obstacle(*cell)

        # SINGLE multi-net route_all call — this is the architectural fix.
        router = self.router_class(self.grid, **self.router_kwargs)
        router_result = router.route_all(all_nets)

        # Post-process: enforce 1-cell physical spacing between routed nets
        # by checking committed intersections. If any two routed paths are
        # adjacent, we flag that for the user (routers like Bundle, Smooth,
        # Hybrid enforce spacing natively via their cost field; sequential
        # ones do not).
        committed_with_margin: set[tuple[int, int]] = set()
        for nr in router_result.nets:
            if not nr.success:
                continue
            for r, c in nr.path:
                committed_with_margin.add((r, c))

        # Build per-net PF components
        self.results = []
        total_wl = 0
        all_rows = set()

        for tp, net_def, net_res in zip(self.terminal_pairs, all_nets, router_result.nets):
            route_layer = layer if layer is not None else tp.terminal1.routing_layer

            if not net_res.success:
                self.results.append(PFRouteResult(name=tp.name, success=False))
                continue

            total_wl += net_res.length
            for r, c in net_res.path:
                all_rows.add(r)

            # Build the PF trace as pf.Path using simplified corner
            # waypoints (faithful to the grid plan). route_manhattan
            # re-routes independently of other nets and introduces
            # collisions, so we don't use it — the trace literally follows
            # the grid-planned centerline. Starting at pad center means the
            # trace overlaps the pad body by ~50 um, which is electrically
            # fine and matches the planning view exactly.
            simplified = simplify_grid_path(net_res.path)
            waypoints = grid_path_to_layout_waypoints(self.gm, simplified)
            comp = self._create_route_component(
                tp.name, waypoints, trace_width, route_layer,
            )
            # Prefix with "route_" so DRC can distinguish traces from baseline
            try:
                if not comp.name.startswith("route_"):
                    comp.name = f"route_{tp.name}"
            except Exception:
                pass
            self.results.append(PFRouteResult(
                name=tp.name, success=True,
                waypoints=waypoints, component=comp,
            ))

        # Store aggregate stats
        self.total_wirelength = total_wl
        self.bundle_width = (max(all_rows) - min(all_rows) + 1) if all_rows else 0
        self.nets_routed = sum(1 for r in self.results if r.success)
        self.router_result = router_result  # expose for diagnostics

        return self.results

    def _create_route_component(
        self,
        name: str,
        waypoints: list[tuple[float, float]],
        trace_width: float,
        layer,
    ) -> pf.Component:
        """Legacy: simple pf.Path between waypoints. Leaves trace starting
        at the first waypoint, overlapping pad body if waypoint is inside."""
        comp = pf.Component(f"route_{name}")
        if len(waypoints) < 2:
            return comp
        path = pf.Path(waypoints[0], trace_width).segment(waypoints[1:])
        comp.add(layer, path)
        return comp

    def _create_route_component_manhattan(
        self,
        name: str,
        terminal1,
        terminal2,
        waypoints: list[tuple[float, float]],
        trace_width: float,
        layer,
        source_dir=None,
        target_dir=None,
        overlap_fraction=(0.15, 0.8),
    ) -> pf.Component:
        """
        Use pf.parametric.route_manhattan with grid-planned corner waypoints.
        Handles terminal contact cleanly (no trace overlapping pad interior).

        overlap_fraction: (at source, at target). 0.15 = trace dips 15% into
        the source (bondpad, large). 0.8 = 80% into target (AMZI pad, tiny
        — need strong contact).

        source_dir / target_dir: "N"/"S"/"E"/"W" or None. Mapped to PF's
        "x"/"y" axis convention.
        """
        # Drop intermediate waypoints that lie inside either terminal bbox
        # (route_manhattan will add its own terminal-overlap segments).
        def _in_bb(xy, term):
            (x1, y1), (x2, y2) = term.bounds()
            return x1 <= xy[0] <= x2 and y1 <= xy[1] <= y2
        mid = [w for w in waypoints[1:-1]
               if not _in_bb(w, terminal1) and not _in_bb(w, terminal2)]

        # PF direction: "x" or "y" (axis), NOT N/S/E/W
        def _to_axis(d):
            if d in ("N", "S"):
                return "y"
            if d in ("E", "W"):
                return "x"
            return None
        d1 = _to_axis(source_dir)
        d2 = _to_axis(target_dir)

        try:
            route_kwargs = dict(
                terminal1=terminal1, terminal2=terminal2,
                layer=layer, width=trace_width,
                overlap_fraction=overlap_fraction,
                name=f"route_{name}",
            )
            if mid:
                route_kwargs["waypoints"] = mid
            if d1: route_kwargs["direction1"] = d1
            if d2: route_kwargs["direction2"] = d2
            return pf.parametric.route_manhattan(**route_kwargs)
        except Exception as exc:
            # Fallback to legacy path if route_manhattan rejects our waypoints
            print(f"  [warn] route_manhattan failed for {name}: {exc}, using pf.Path")
            return self._create_route_component(name, waypoints, trace_width, layer)

    def summary(self) -> str:
        algo = self.router_class.name
        ok = getattr(self, 'nets_routed', 0)
        total = len(self.results)
        wl = getattr(self, 'total_wirelength', 0)
        bw = getattr(self, 'bundle_width', 0)
        lines = [
            f"PFRoutingArena [{algo}]: grid {self.gm.rows}x{self.gm.cols}, "
            f"pitch={self.gm.grid_pitch} um",
            f"  {ok}/{total} nets, wirelength={wl}, bundle_width={bw}",
        ]
        for r in self.results:
            status = "OK" if r.success else "FAIL"
            lines.append(f"  [{status}] {r.name}: {len(r.waypoints)} wp")
        return "\n".join(lines)
