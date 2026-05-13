"""
Pass/fail criteria for AMZI bondpad routing experiments.

Hard rules (must ALL pass):
  all_routed            — every net has a non-empty path
  no_m1_crossing        — no route cell sits on an M1_heater cell
                          (M2 over M1 heater = heatsink = dead phase shifter)
  no_pad_crossing       — no route cell sits inside another net's pad footprint
                          (would short the other net's trace into the pad)
  no_route_crossing     — no two routes share a cell (single-layer assumption)
  no_pad_overlap        — no two pads overlap in the layout

Soft metrics (rank PASS configs by these):
  bundling_score        — fraction of route cells that have a ≥ k-cell parallel
                          neighbor run (higher = more "bunched")
  total_wirelength      — sum of path lengths in cells
  max_turns_per_net     — worst single-net turn count (lower = cleaner)
  avg_turns_per_net     — average turn count
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class RouteScore:
    # Hard rules
    all_routed: bool
    no_m1_crossing: bool
    no_pad_crossing: bool
    no_route_crossing: bool
    no_pad_overlap: bool
    # Soft metrics
    nets_routed: int
    nets_total: int
    total_wirelength: int
    max_turns: int
    avg_turns: float
    bundling_score: float
    # Diagnostics
    failed_nets: list = field(default_factory=list)
    m1_violations: list = field(default_factory=list)   # list of (net_name, cell)
    pad_violations: list = field(default_factory=list)  # list of (net_name, cell, blocking_net)
    route_violations: list = field(default_factory=list) # list of (cell, [net names])

    @property
    def passes(self) -> bool:
        return (self.all_routed and self.no_m1_crossing and
                self.no_pad_crossing and self.no_route_crossing and
                self.no_pad_overlap)

    def summary(self) -> str:
        flag = "✓" if self.passes else "✗"
        rules = []
        rules.append(f"routed={self.nets_routed}/{self.nets_total}")
        if not self.no_m1_crossing:
            rules.append(f"M1 crosses={len(self.m1_violations)}")
        if not self.no_pad_crossing:
            rules.append(f"pad crosses={len(self.pad_violations)}")
        if not self.no_route_crossing:
            rules.append(f"route crosses={len(self.route_violations)}")
        if not self.no_pad_overlap:
            rules.append(f"pad overlaps")
        return (f"{flag} {self.nets_routed}/{self.nets_total} · "
                f"wl={self.total_wirelength} · bund={self.bundling_score:.2f} · "
                f"turns={self.avg_turns:.1f}/{self.max_turns} · "
                + " ".join(rules))


def _count_turns(path):
    """Count direction changes along a grid path."""
    if len(path) < 3:
        return 0
    turns = 0
    for i in range(2, len(path)):
        d1 = (path[i-1][0]-path[i-2][0], path[i-1][1]-path[i-2][1])
        d2 = (path[i][0]-path[i-1][0], path[i][1]-path[i-1][1])
        if d1 != d2:
            turns += 1
    return turns


def _bundling_score(result_nets, k: int = 3) -> float:
    """
    Fraction of route cells that have at least one neighbor belonging to a
    DIFFERENT successful net, over a run of length ≥ k.

    Intuition: bundled traces run parallel for long distances. A perfectly
    isolated trace has 0; a trace whose entire length has a neighbor ≥ k
    cells long scores close to 1.
    """
    # Build map: cell -> list[net_name]
    cell_owner = {}
    for nr in result_nets:
        if not nr.success:
            continue
        for rc in nr.path:
            cell_owner.setdefault(rc, []).append(nr.net_name)

    # For each net cell, check if a 4-neighbor belongs to ANOTHER net
    net_cells_with_parallel = {}
    for nr in result_nets:
        if not nr.success:
            continue
        parallel_cells = set()
        for (r, c) in nr.path:
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nb = (r+dr, c+dc)
                owners = cell_owner.get(nb, [])
                if any(o != nr.net_name for o in owners):
                    parallel_cells.add((r, c))
                    break
        # Keep only runs of ≥ k consecutive parallel cells along the path
        long_run_cells = set()
        run = []
        for rc in nr.path:
            if rc in parallel_cells:
                run.append(rc)
            else:
                if len(run) >= k:
                    long_run_cells.update(run)
                run = []
        if len(run) >= k:
            long_run_cells.update(run)
        net_cells_with_parallel[nr.net_name] = (len(long_run_cells), len(nr.path))

    total_parallel = sum(p for p, _ in net_cells_with_parallel.values())
    total_cells = sum(t for _, t in net_cells_with_parallel.values())
    return (total_parallel / total_cells) if total_cells else 0.0


def score_result(result, nets, m1_cells: set, trace_cells_by_net: dict = None) -> RouteScore:
    """
    Score a RouterResult against the routing criteria.

    Args:
      result: RouterResult (from routing_algorithms.py)
      nets:   list of net dicts (same order as result.nets). Each must have
              "footprint" (set of cells) and "_is_top"/other metadata.
      m1_cells: set of (r, c) cells on M1_heater layer
      trace_cells_by_net: optional precomputed {net_name: set(cells)}. If
              omitted, derived from result.nets[i].path.
    """
    # ── per-net paths ──
    if trace_cells_by_net is None:
        trace_cells_by_net = {
            nr.net_name: set(nr.path) for nr in result.nets if nr.success
        }

    # ── all_routed ──
    nets_routed = sum(1 for nr in result.nets if nr.success)
    nets_total = len(result.nets)
    all_routed = (nets_routed == nets_total)
    failed_nets = [nr.net_name for nr in result.nets if not nr.success]

    # ── no_m1_crossing ──
    # A route "crosses" M1 if it passes over an M1_heater cell in the body
    # of its path (resistor region). M1 cells INSIDE any terminal footprint
    # are contact pads — touching them is the intended bondpad-to-heater
    # electrical connection, NOT a heatsink crossing.
    # So: a violation is an M1 cell that is NOT within any net's footprint.
    all_footprint_cells = set()
    for n in nets:
        all_footprint_cells |= set(n.get("footprint", ()))
    m1_violations = []
    for nr in result.nets:
        if not nr.success or len(nr.path) < 2:
            continue
        for cell in nr.path:
            if cell in m1_cells and cell not in all_footprint_cells:
                m1_violations.append((nr.net_name, cell))
    no_m1_crossing = len(m1_violations) == 0

    # ── no_pad_crossing ──
    # Each net's path must not pass through another net's pad footprint
    # (excluding the route's own endpoints, which are inside its own footprint).
    footprint_by_net = {n["name"]: set(n.get("footprint", ())) for n in nets}
    pad_violations = []
    for nr in result.nets:
        if not nr.success or len(nr.path) < 2:
            continue
        interior = nr.path[1:-1] if len(nr.path) > 2 else []
        own_fp = footprint_by_net.get(nr.net_name, set())
        for cell in interior:
            if cell in own_fp:
                continue  # own pad, fine
            for other_name, other_fp in footprint_by_net.items():
                if other_name == nr.net_name:
                    continue
                if cell in other_fp:
                    pad_violations.append((nr.net_name, cell, other_name))
                    break
    no_pad_crossing = len(pad_violations) == 0

    # ── no_route_crossing ──
    # Two routes cannot share a non-terminal cell. Terminals may be shared
    # (not our case, but safer).
    cell_users = {}
    for nr in result.nets:
        if not nr.success:
            continue
        # Interior cells only — endpoints are terminals and belong to only one net anyway
        interior = nr.path[1:-1] if len(nr.path) > 2 else []
        for cell in interior:
            cell_users.setdefault(cell, []).append(nr.net_name)
    route_violations = [(c, users) for c, users in cell_users.items() if len(users) > 1]
    no_route_crossing = len(route_violations) == 0

    # ── no_pad_overlap ──
    # Two pads physically overlap if their SOURCE or TARGET grid cells
    # collide. Footprint margin overlap is fine — that's just safety padding.
    endpoints = {}
    pad_overlaps = []
    for n in nets:
        for key in ("source", "target"):
            cell = tuple(n[key])
            if cell in endpoints and endpoints[cell] != n["name"]:
                pad_overlaps.append((endpoints[cell], n["name"], cell))
            else:
                endpoints[cell] = n["name"]
    no_pad_overlap = len(pad_overlaps) == 0

    # ── soft metrics ──
    total_wirelength = sum(len(nr.path) for nr in result.nets if nr.success)
    turns = [_count_turns(nr.path) for nr in result.nets if nr.success]
    max_turns = max(turns) if turns else 0
    avg_turns = (sum(turns) / len(turns)) if turns else 0.0
    bundling = _bundling_score(result.nets)

    return RouteScore(
        all_routed=all_routed,
        no_m1_crossing=no_m1_crossing,
        no_pad_crossing=no_pad_crossing,
        no_route_crossing=no_route_crossing,
        no_pad_overlap=no_pad_overlap,
        nets_routed=nets_routed,
        nets_total=nets_total,
        total_wirelength=total_wirelength,
        max_turns=max_turns,
        avg_turns=avg_turns,
        bundling_score=bundling,
        failed_nets=failed_nets,
        m1_violations=m1_violations[:20],  # cap for printing
        pad_violations=pad_violations[:20],
        route_violations=route_violations[:20],
    )


if __name__ == "__main__":
    # Self-test: import and run a fake scoring to verify structure
    from dataclasses import dataclass
    @dataclass
    class FakeNR:
        net_name: str
        success: bool
        path: list
    @dataclass
    class FakeR:
        nets: list
    r = FakeR(nets=[
        FakeNR("N0", True, [(0,0),(0,1),(0,2),(0,3)]),
        FakeNR("N1", True, [(1,0),(1,1),(1,2),(1,3)]),  # parallel to N0
    ])
    nets = [
        {"name": "N0", "footprint": {(0,0),(0,3)}},
        {"name": "N1", "footprint": {(1,0),(1,3)}},
    ]
    score = score_result(r, nets, m1_cells=set())
    print(score.summary())
    print(f"  bundling={score.bundling_score:.3f}  (expect high because N0 and N1 parallel)")
