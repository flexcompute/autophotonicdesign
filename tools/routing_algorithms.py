"""
routing_algorithms.py — Comparative Routing Algorithm Framework

A unified framework for comparing PCB/VLSI routing algorithms.
All routers share a common base class and produce comparable results.

Algorithms:
  1. SequentialBFS     — Lee's Algorithm, route one net at a time
  2. AStarRouter       — A* with Manhattan heuristic, sequential
  3. BundleRouter      — Cost field attraction + Dijkstra (our original)
  4. RiverRouter       — Maintains net ordering, routes as parallel flow
  5. NegotiationRouter — PathFinder-style: all nets route, then negotiate congestion
  6. RipUpRouter       — Multi-pass rip-up-and-reroute with escalating costs

Usage:
    from routing_algorithms import (
        SequentialBFS, AStarRouter, BundleRouter,
        RiverRouter, NegotiationRouter, RipUpRouter,
        Grid, compare_routers
    )

    grid = Grid(50, 80)
    grid.add_obstacle_line(25, 10, 25, 70)  # horizontal wall

    nets = [
        {"name": "D0", "source": (5, 0),  "target": (5, 79)},
        {"name": "D1", "source": (12, 0), "target": (12, 79)},
        {"name": "D2", "source": (20, 0), "target": (20, 79)},
        {"name": "D3", "source": (35, 0), "target": (35, 79)},
    ]

    results = compare_routers(grid, nets, [
        SequentialBFS, AStarRouter, BundleRouter,
        RiverRouter, NegotiationRouter, RipUpRouter
    ])
    for name, res in results.items():
        print(f"{name}: {res.summary()}")
"""

from __future__ import annotations
import heapq
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


# ════════════════════════════════════════════════════════════════
# SHARED DATA TYPES
# ════════════════════════════════════════════════════════════════

DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIR_NAMES = {(-1, 0): 'N', (1, 0): 'S', (0, -1): 'W', (0, 1): 'E'}
NAME_TO_DIR = {'N': (-1, 0), 'S': (1, 0), 'W': (0, -1), 'E': (0, 1)}
OPPOSITE = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}


@dataclass
class NetResult:
    """Result for a single routed net."""
    net_name: str
    source: tuple[int, int]
    target: tuple[int, int]
    success: bool
    path: list[tuple[int, int]] = field(default_factory=list)
    cost: float = 0.0

    @property
    def length(self) -> int:
        return len(self.path)


@dataclass
class RouterResult:
    """Aggregate result from a router run."""
    algorithm: str
    nets: list[NetResult] = field(default_factory=list)
    iterations: int = 0
    time_ms: float = 0.0

    @property
    def total_wirelength(self) -> int:
        return sum(n.length for n in self.nets if n.success)

    @property
    def nets_routed(self) -> int:
        return sum(1 for n in self.nets if n.success)

    @property
    def bundle_width(self) -> int:
        """Max row span across all paths — measures how compact the bundle is."""
        all_rows = set()
        for n in self.nets:
            if n.success:
                for r, c in n.path:
                    all_rows.add(r)
        return (max(all_rows) - min(all_rows) + 1) if all_rows else 0

    def summary(self) -> str:
        ok = self.nets_routed
        total = len(self.nets)
        wl = self.total_wirelength
        bw = self.bundle_width
        return (f"{self.algorithm}: {ok}/{total} nets, wirelength={wl}, "
                f"bundle_width={bw}, iters={self.iterations}")


class Grid:
    """Shared grid representation for all routers."""

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self.obstacles: set[tuple[int, int]] = set()

    def add_obstacle(self, r: int, c: int):
        if 0 <= r < self.rows and 0 <= c < self.cols:
            self.obstacles.add((r, c))

    def add_obstacle_line(self, r1: int, c1: int, r2: int, c2: int):
        """Add obstacles along a line from (r1,c1) to (r2,c2)."""
        if r1 == r2:
            for c in range(min(c1, c2), max(c1, c2) + 1):
                self.add_obstacle(r1, c)
        elif c1 == c2:
            for r in range(min(r1, r2), max(r1, r2) + 1):
                self.add_obstacle(r, c1)

    def add_obstacle_rect(self, r1: int, c1: int, r2: int, c2: int):
        for r in range(min(r1, r2), max(r1, r2) + 1):
            for c in range(min(c1, c2), max(c1, c2) + 1):
                self.add_obstacle(r, c)

    def make_blocked_set(self, extra_blocked: Optional[set] = None) -> set:
        s = set(self.obstacles)
        if extra_blocked:
            s |= extra_blocked
        return s

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols


# ════════════════════════════════════════════════════════════════
# BASE ROUTER
# ════════════════════════════════════════════════════════════════

class BaseRouter(ABC):
    """Abstract base — all routers implement route_all()."""

    name: str = "BaseRouter"

    def __init__(self, grid: Grid):
        self.grid = grid

    @abstractmethod
    def route_all(self, nets: list[dict]) -> RouterResult:
        """Route all nets and return results."""
        ...

    # ── Shared utilities ────────────────────────────────────────

    def _reserve_pins(self, nets: list[dict], current_idx: int, blocked: set) -> set:
        """Reserve all other nets' pins (and pad footprints, if given) as blocked.

        If a net dict contains a "footprint" key (iterable of (r,c) cells),
        those cells are also reserved for that net — other nets cannot route
        through them. This is how the PhotonForge bridge represents multi-cell
        pad exclusion zones.
        """
        b = set(blocked)
        for i, net in enumerate(nets):
            if i == current_idx:
                continue
            b.add(tuple(net["source"]))
            b.add(tuple(net["target"]))
            for cell in net.get("footprint", ()):
                b.add(tuple(cell))
        return b

    def _apply_pin_directions(self, net: dict, blocked: set) -> set:
        """
        Enforce pin entry/exit direction constraints by blocking
        wrong-direction neighbors around source and target.

        Net dict can optionally include:
          "source_dir": "N"|"S"|"E"|"W" or a tuple/set of those
                        — allowed direction(s) for the trace to EXIT source
          "target_dir": same — allowed direction(s) the trace must ENTER from

        For target_dir="W", the trace must approach from the west side,
        meaning the last step is moving east INTO the target.
        So we block all neighbors of target except the one to the west.

        If target_dir is a set like ("N", "W", "S"), the trace can arrive
        from any of those directions (but not from E). We block only the
        directions NOT in the set.
        """
        b = set(blocked)
        src = tuple(net["source"])
        tgt = tuple(net["target"])

        def _allowed_dirs(spec):
            if spec is None:
                return None  # no constraint
            if isinstance(spec, str):
                return {NAME_TO_DIR[spec]} if spec in NAME_TO_DIR else None
            return {NAME_TO_DIR[d] for d in spec if d in NAME_TO_DIR}

        source_allowed = _allowed_dirs(net.get("source_dir"))
        target_allowed = _allowed_dirs(net.get("target_dir"))

        if source_allowed:
            for dr, dc in DIRS:
                if (dr, dc) in source_allowed:
                    continue
                nr, nc = src[0] + dr, src[1] + dc
                if self.grid.in_bounds(nr, nc) and (nr, nc) != tgt:
                    b.add((nr, nc))

        if target_allowed:
            for dr, dc in DIRS:
                if (dr, dc) in target_allowed:
                    continue
                nr, nc = tgt[0] + dr, tgt[1] + dc
                if self.grid.in_bounds(nr, nc) and (nr, nc) != src:
                    b.add((nr, nc))

        return b

    def _prepare_blocked(self, nets: list[dict], current_idx: int,
                         committed: set) -> set:
        """One-stop method: obstacles + committed + pin reservation + direction constraints.

        Handles a "footprint" key in the current net dict: those cells are
        discharged from blocked so this net can route through its own pad.
        """
        blocked = self.grid.make_blocked_set(committed)
        blocked = self._reserve_pins(nets, current_idx, blocked)
        net = nets[current_idx]
        blocked.discard(tuple(net["source"]))
        blocked.discard(tuple(net["target"]))
        for cell in net.get("footprint", ()):
            blocked.discard(tuple(cell))
        blocked = self._apply_pin_directions(net, blocked)
        return blocked

    def _bfs(self, source, target, blocked: set) -> list[tuple[int, int]]:
        """Standard BFS shortest path."""
        src, tgt = tuple(source), tuple(target)
        if src in blocked or tgt in blocked:
            return []
        parent = {src: None}
        queue = deque([src])
        while queue:
            r, c = queue.popleft()
            if (r, c) == tgt:
                break
            for dr, dc in DIRS:
                nr, nc = r + dr, c + dc
                if not self.grid.in_bounds(nr, nc):
                    continue
                if (nr, nc) in parent or (nr, nc) in blocked:
                    continue
                parent[(nr, nc)] = (r, c)
                if (nr, nc) == tgt:
                    break
                queue.append((nr, nc))
        if tgt not in parent:
            return []
        path = []
        cell = tgt
        while cell is not None:
            path.append(cell)
            cell = parent[cell]
        path.reverse()
        return path

    def _astar(self, source, target, blocked: set,
               cost_fn=None) -> tuple[list[tuple[int, int]], float]:
        """A* with optional cost function. Returns (path, total_cost)."""
        src, tgt = tuple(source), tuple(target)
        if src in blocked or tgt in blocked:
            return [], float('inf')

        def heuristic(r, c):
            return abs(r - tgt[0]) + abs(c - tgt[1])

        dist = {src: 0.0}
        parent = {src: None}
        heap = [(heuristic(src[0], src[1]), 0.0, src)]

        while heap:
            _, d, (r, c) = heapq.heappop(heap)
            if d > dist.get((r, c), float('inf')):
                continue
            if (r, c) == tgt:
                break
            for dr, dc in DIRS:
                nr, nc = r + dr, c + dc
                if not self.grid.in_bounds(nr, nc) or (nr, nc) in blocked:
                    continue
                edge_cost = cost_fn(nr, nc) if cost_fn else 1.0
                if edge_cost >= 1e20:
                    continue
                nd = d + edge_cost
                if nd < dist.get((nr, nc), float('inf')):
                    dist[(nr, nc)] = nd
                    parent[(nr, nc)] = (r, c)
                    heapq.heappush(heap, (nd + heuristic(nr, nc), nd, (nr, nc)))

        if tgt not in dist or dist[tgt] == float('inf'):
            return [], float('inf')

        path = []
        cell = tgt
        while cell is not None:
            path.append(cell)
            cell = parent[cell]
        path.reverse()
        return path, dist[tgt]

    def _build_distance_field(self, seeds: set, blocked: set,
                              max_radius: int = 30) -> dict[tuple[int, int], int]:
        """Multi-source BFS distance from seed cells.

        Attraction does NOT propagate through blocked cells — this prevents
        cost-field leakage through walls which would mis-steer Bundle /
        SmoothBundle / Hybrid routers toward cells they can't legally reach.
        Seeds are always included at distance 0 even if they appear in blocked
        (committed route cells are a typical case).
        """
        dist = {}
        queue = deque()
        for s in seeds:
            dist[s] = 0
            queue.append(s)
        while queue:
            r, c = queue.popleft()
            if dist[(r, c)] >= max_radius:
                continue
            for dr, dc in DIRS:
                nr, nc = r + dr, c + dc
                if not self.grid.in_bounds(nr, nc):
                    continue
                if (nr, nc) in blocked:
                    continue
                if (nr, nc) not in dist:
                    dist[(nr, nc)] = dist[(r, c)] + 1
                    queue.append((nr, nc))
        return dist


# ════════════════════════════════════════════════════════════════
# 1. SEQUENTIAL BFS (Lee's Algorithm)
# ════════════════════════════════════════════════════════════════

class SequentialBFS(BaseRouter):
    """Classic Lee's Algorithm — route nets one at a time via BFS."""

    name = "Sequential BFS"

    def route_all(self, nets):
        result = RouterResult(algorithm=self.name)
        committed = set()

        for i, net in enumerate(nets):
            blocked = self._prepare_blocked(nets, i, committed)
            path = self._bfs(net["source"], net["target"], blocked)
            nr = NetResult(
                net_name=net.get("name", f"net{i}"),
                source=tuple(net["source"]),
                target=tuple(net["target"]),
                success=len(path) > 0,
                path=path,
                cost=len(path),
            )
            result.nets.append(nr)
            if nr.success:
                committed.update(path)

        return result


# ════════════════════════════════════════════════════════════════
# 2. A* ROUTER (Manhattan heuristic)
# ════════════════════════════════════════════════════════════════

class AStarRouter(BaseRouter):
    """Sequential A* with Manhattan distance heuristic."""

    name = "A* Router"

    def route_all(self, nets):
        result = RouterResult(algorithm=self.name)
        committed = set()

        for i, net in enumerate(nets):
            blocked = self._prepare_blocked(nets, i, committed)
            path, cost = self._astar(net["source"], net["target"], blocked)
            nr = NetResult(
                net_name=net.get("name", f"net{i}"),
                source=tuple(net["source"]),
                target=tuple(net["target"]),
                success=len(path) > 0,
                path=path,
                cost=cost,
            )
            result.nets.append(nr)
            if nr.success:
                committed.update(path)

        return result


# ════════════════════════════════════════════════════════════════
# 3. BUNDLE ROUTER (Cost Field + Dijkstra)
# ════════════════════════════════════════════════════════════════

class BundleRouter(BaseRouter):
    """
    Our attraction-field approach.
    First net via BFS, subsequent nets via Dijkstra on a cost field
    that attracts toward existing routes.
    """

    name = "Bundle Router"

    def __init__(self, grid, spacing=1, sweet_spot=2,
                 attract_cost=0.2, falloff=0.5, stray_cost=5.0):
        super().__init__(grid)
        self.spacing = spacing
        self.sweet_spot = sweet_spot
        self.attract_cost = attract_cost
        self.falloff = falloff
        self.stray_cost = stray_cost

    def _build_cost_field(self, committed: set, blocked: set) -> dict:
        """Build cost lookup from distance to committed routes."""
        if not committed:
            return {}
        dist = self._build_distance_field(
            committed, blocked,
            max_radius=self.sweet_spot + int(self.stray_cost / max(self.falloff, 0.01)) + 2
        )
        cost_map = {}
        for cell, d in dist.items():
            if cell in blocked:
                continue
            if d == 0:
                continue  # on a route — blocked
            if d <= self.spacing:
                continue  # too close — blocked
            if d == self.sweet_spot:
                cost_map[cell] = self.attract_cost
            elif d < self.sweet_spot:
                t = (d - self.spacing) / max(self.sweet_spot - self.spacing, 1)
                cost_map[cell] = 1.0 + t * (self.attract_cost - 1.0)
            else:
                cost_map[cell] = min(
                    self.attract_cost + (d - self.sweet_spot) * self.falloff,
                    self.stray_cost
                )
        return cost_map

    def route_all(self, nets):
        result = RouterResult(algorithm=self.name)
        committed = set()

        for i, net in enumerate(nets):
            blocked = self._prepare_blocked(nets, i, committed)

            if i == 0:
                path = self._bfs(net["source"], net["target"], blocked)
                cost = float(len(path))
            else:
                # Build attraction cost field
                cost_field = self._build_cost_field(committed, blocked)

                # Cells in spacing zone are also blocked
                spacing_blocked = set(blocked)
                if committed:
                    dist = self._build_distance_field(committed, blocked, self.spacing)
                    for cell, d in dist.items():
                        if 0 < d <= self.spacing:
                            spacing_blocked.add(cell)
                spacing_blocked.discard(tuple(net["source"]))
                spacing_blocked.discard(tuple(net["target"]))

                def cost_fn(r, c):
                    if (r, c) in spacing_blocked:
                        return 1e30
                    return cost_field.get((r, c), 1.0)

                path, cost = self._astar(net["source"], net["target"],
                                         spacing_blocked, cost_fn=cost_fn)

            nr = NetResult(
                net_name=net.get("name", f"net{i}"),
                source=tuple(net["source"]),
                target=tuple(net["target"]),
                success=len(path) > 0,
                path=path,
                cost=cost,
            )
            result.nets.append(nr)
            if nr.success:
                committed.update(path)

        return result


# ════════════════════════════════════════════════════════════════
# 4. RIVER ROUTER
# ════════════════════════════════════════════════════════════════

class RiverRouter(BaseRouter):
    """
    River routing: maintains topological ordering of nets.

    Approach:
    1. Route the "center" net first (median by source row)
    2. Route adjacent nets outward, biasing each to run on the
       correct side of already-routed nets (above or below)
    3. Uses A* with a directional bias cost to maintain ordering
    """

    name = "River Router"

    def __init__(self, grid, lane_spacing=2, order_penalty=3.0):
        super().__init__(grid)
        self.lane_spacing = lane_spacing
        self.order_penalty = order_penalty

    def route_all(self, nets):
        result = RouterResult(algorithm=self.name)

        # Sort nets by source row to establish topological order
        indexed = [(i, net) for i, net in enumerate(nets)]
        indexed.sort(key=lambda x: x[1]["source"][0])

        # Route from center outward (interleave above/below)
        mid = len(indexed) // 2
        order = [indexed[mid]]
        above, below = mid - 1, mid + 1
        while above >= 0 or below < len(indexed):
            if below < len(indexed):
                order.append(indexed[below])
                below += 1
            if above >= 0:
                order.append(indexed[above])
                above -= 1

        committed = set()
        committed_paths = {}  # net_original_idx -> path
        net_results = [None] * len(nets)

        for seq, (orig_idx, net) in enumerate(order):
            blocked = self._prepare_blocked(nets, orig_idx, committed)

            if seq == 0:
                path = self._bfs(net["source"], net["target"], blocked)
                cost = float(len(path))
            else:
                # Build directional bias: this net should stay on its
                # "side" relative to already-routed nets
                src_row = net["source"][0]
                # Find avg row of committed paths
                if committed:
                    avg_row = sum(r for r, c in committed) / len(committed)
                else:
                    avg_row = self.grid.rows / 2

                desired_side = 1 if src_row > avg_row else -1  # +1 = below, -1 = above

                def cost_fn(r, c):
                    if (r, c) in blocked:
                        return 1e30
                    base = 1.0
                    # Penalize crossing to wrong side
                    if committed:
                        # Distance from center of existing routes
                        deviation = (r - avg_row) * desired_side
                        if deviation < 0:
                            # Wrong side — heavy penalty
                            base += self.order_penalty * abs(deviation)
                        elif deviation < self.lane_spacing:
                            # Too close to existing routes
                            base += 2.0
                    return base

                path, cost = self._astar(net["source"], net["target"],
                                         blocked, cost_fn=cost_fn)

            nr = NetResult(
                net_name=net.get("name", f"net{orig_idx}"),
                source=tuple(net["source"]),
                target=tuple(net["target"]),
                success=len(path) > 0,
                path=path,
                cost=cost,
            )
            net_results[orig_idx] = nr
            if nr.success:
                committed.update(path)
                committed_paths[orig_idx] = path

        result.nets = net_results
        return result


# ════════════════════════════════════════════════════════════════
# 5. NEGOTIATION-BASED ROUTER (PathFinder-style)
# ════════════════════════════════════════════════════════════════

class NegotiationRouter(BaseRouter):
    """
    PathFinder-style negotiation-based router.

    All nets route simultaneously in each iteration. Cells used by
    multiple nets get increasing "congestion cost." Over iterations,
    nets reroute around congested areas.

    Key formula: cost(cell) = base + history_cost * h_fac + present_congestion * p_fac
    """

    name = "Negotiation Router"

    def __init__(self, grid, max_iterations=15, p_fac=1.5, h_fac_initial=0.5,
                 h_fac_growth=1.0):
        super().__init__(grid)
        self.max_iterations = max_iterations
        self.p_fac = p_fac
        self.h_fac_initial = h_fac_initial
        self.h_fac_growth = h_fac_growth

    def route_all(self, nets):
        result = RouterResult(algorithm=self.name)
        ROWS, COLS = self.grid.rows, self.grid.cols

        # History congestion (accumulates across iterations)
        history = {}  # (r,c) -> accumulated overuse
        best_paths = [None] * len(nets)
        best_result = None
        # Local h_fac so repeat calls to route_all start fresh
        h_fac = self.h_fac_initial

        for iteration in range(self.max_iterations):
            # Present congestion: how many nets use each cell this iteration
            occupancy = {}  # (r,c) -> count
            current_paths = [None] * len(nets)

            for i, net in enumerate(nets):
                src, tgt = tuple(net["source"]), tuple(net["target"])
                # Use the shared helper so footprints + pin dirs are handled
                # correctly. Negotiation doesn't have a "committed" set — each
                # iteration is simultaneous — so pass empty committed.
                blocked = self._prepare_blocked(nets, i, set())

                def cost_fn(r, c, _h_fac=h_fac):
                    if (r, c) in blocked:
                        return 1e30
                    base = 1.0
                    h = history.get((r, c), 0) * _h_fac
                    p = occupancy.get((r, c), 0) * self.p_fac
                    return base + h + p

                path, cost = self._astar(src, tgt, blocked, cost_fn=cost_fn)
                current_paths[i] = path

                # Update occupancy
                if path:
                    for cell in path:
                        occupancy[cell] = occupancy.get(cell, 0) + 1

            # Check for conflicts (cells used by > 1 net)
            conflicts = {cell for cell, count in occupancy.items() if count > 1}

            # Update history
            for cell in conflicts:
                history[cell] = history.get(cell, 0) + 1

            # Increase history factor (local — don't mutate instance)
            h_fac += self.h_fac_growth

            # Score this iteration
            all_success = all(p and len(p) > 0 for p in current_paths)
            if len(conflicts) == 0 and all_success:
                best_paths = current_paths
                result.iterations = iteration + 1
                break

            # Keep best so far (fewest conflicts)
            if best_result is None or len(conflicts) < best_result:
                best_result = len(conflicts)
                best_paths = list(current_paths)

            result.iterations = iteration + 1

        # Finalize: resolve any remaining conflicts by sequential reroute
        committed = set()
        for i, net in enumerate(nets):
            path = best_paths[i] if best_paths[i] else []

            # If path has conflicts with committed, re-route around them
            if path and committed.intersection(path):
                blocked = self._prepare_blocked(nets, i, committed)
                path = self._bfs(net["source"], net["target"], blocked)

            nr = NetResult(
                net_name=net.get("name", f"net{i}"),
                source=tuple(net["source"]),
                target=tuple(net["target"]),
                success=len(path) > 0,
                path=path,
                cost=float(len(path)),
            )
            result.nets.append(nr)
            if nr.success:
                committed.update(path)

        return result


# ════════════════════════════════════════════════════════════════
# 6. RIP-UP AND REROUTE
# ════════════════════════════════════════════════════════════════

class RipUpRouter(BaseRouter):
    """
    Multi-pass rip-up-and-reroute.

    Pass 1: Route all nets sequentially (may fail some).
    Pass 2+: For each failed net, rip up the blocking net with
    the worst cost/benefit ratio, reroute both.
    Uses escalating costs for repeatedly-ripped nets.
    """

    name = "Rip-Up Router"

    def __init__(self, grid, max_passes=8):
        super().__init__(grid)
        self.max_passes = max_passes

    def route_all(self, nets):
        result = RouterResult(algorithm=self.name)
        n = len(nets)

        # Track: net_idx -> path (or empty)
        paths = [[] for _ in range(n)]
        rip_count = [0] * n  # how many times each net was ripped

        # Pass 1: sequential BFS
        committed = set()
        for i, net in enumerate(nets):
            blocked = self._prepare_blocked(nets, i, committed)
            path = self._bfs(net["source"], net["target"], blocked)
            paths[i] = path
            if path:
                committed.update(path)

        total_iters = 1

        # Subsequent passes: rip-up failed nets
        for pass_num in range(1, self.max_passes):
            failed = [i for i in range(n) if not paths[i]]
            if not failed:
                break

            improved = False
            for fi in failed:
                fnet = nets[fi]
                fsrc, ftgt = tuple(fnet["source"]), tuple(fnet["target"])

                # Find which committed nets block us
                # Try ripping each other net and see if fi can route
                best_rip = None
                best_rip_cost = float('inf')

                for ri in range(n):
                    if ri == fi or not paths[ri]:
                        continue
                    # Cost of ripping: path length × (1 + rip_count)
                    rip_cost = len(paths[ri]) * (1 + rip_count[ri])

                    # Would removing ri's path let fi route?
                    test_committed = set()
                    for j in range(n):
                        if j == ri or j == fi:
                            continue
                        test_committed.update(paths[j])

                    blocked = self._prepare_blocked(nets, fi, test_committed)
                    test_path = self._bfs(fnet["source"], fnet["target"], blocked)

                    if test_path and rip_cost < best_rip_cost:
                        best_rip = ri
                        best_rip_cost = rip_cost

                if best_rip is not None:
                    # Rip the chosen net
                    rip_count[best_rip] += 1
                    old_path = paths[best_rip]
                    paths[best_rip] = []

                    # Route the failed net
                    committed = set()
                    for j in range(n):
                        committed.update(paths[j])

                    blocked = self._prepare_blocked(nets, fi, committed)
                    new_path = self._bfs(fnet["source"], fnet["target"], blocked)
                    if new_path:
                        paths[fi] = new_path
                        committed.update(new_path)

                    # Re-route the ripped net
                    rnet = nets[best_rip]
                    blocked2 = self._prepare_blocked(nets, best_rip, committed)
                    repath = self._bfs(rnet["source"], rnet["target"], blocked2)
                    paths[best_rip] = repath
                    if repath:
                        committed.update(repath)

                    improved = True

            total_iters += 1
            if not improved:
                break

        # Build results
        result.iterations = total_iters
        for i, net in enumerate(nets):
            nr = NetResult(
                net_name=net.get("name", f"net{i}"),
                source=tuple(net["source"]),
                target=tuple(net["target"]),
                success=len(paths[i]) > 0,
                path=paths[i],
                cost=float(len(paths[i])),
            )
            result.nets.append(nr)

        return result


# ════════════════════════════════════════════════════════════════
# 7. SMOOTH BUNDLE ROUTER (Bundle + turn penalty)
# ════════════════════════════════════════════════════════════════

class SmoothBundleRouter(BaseRouter):
    """
    Bundle Router with turn-cost penalty.
    State includes direction so turns are penalized — suppresses
    the zig-zag oscillation seen in basic Bundle Router.
    """

    name = "Smooth Bundle"

    def __init__(self, grid, spacing=1, sweet_spot=2,
                 attract_cost=0.2, falloff=0.5, stray_cost=5.0,
                 turn_cost=0.4):
        super().__init__(grid)
        self.spacing = spacing
        self.sweet_spot = sweet_spot
        self.attract_cost = attract_cost
        self.falloff = falloff
        self.stray_cost = stray_cost
        self.turn_cost = turn_cost

    def _build_cost_field(self, committed, blocked):
        if not committed:
            return {}
        dist = self._build_distance_field(
            committed, blocked,
            max_radius=self.sweet_spot + int(self.stray_cost / max(self.falloff, 0.01)) + 2
        )
        cost_map = {}
        for cell, d in dist.items():
            if cell in blocked:
                continue
            if d == 0 or d <= self.spacing:
                continue
            if d == self.sweet_spot:
                cost_map[cell] = self.attract_cost
            elif d < self.sweet_spot:
                t = (d - self.spacing) / max(self.sweet_spot - self.spacing, 1)
                cost_map[cell] = 1.0 + t * (self.attract_cost - 1.0)
            else:
                cost_map[cell] = min(
                    self.attract_cost + (d - self.sweet_spot) * self.falloff,
                    self.stray_cost
                )
        return cost_map

    def _astar_with_turns(self, source, target, blocked, cost_fn, turn_cost):
        """A* where state = (r, c, direction). Turn changes cost extra."""
        src, tgt = tuple(source), tuple(target)
        if src in blocked or tgt in blocked:
            return [], float('inf')

        def h(r, c):
            return abs(r - tgt[0]) + abs(c - tgt[1])

        INF = float('inf')
        # State: (r, c, dir_idx) where dir_idx = 0-3 for DIRS, 4 = start
        dist = {}
        parent = {}
        heap = []
        # Start with all directions possible (dir=4 means "any")
        start = (src[0], src[1], 4)
        dist[start] = 0.0
        parent[start] = None
        counter = 0  # tiebreaker for heapq
        heapq.heappush(heap, (h(src[0], src[1]), counter, start))
        counter += 1

        while heap:
            f, _, state = heapq.heappop(heap)
            r, c, di = state
            d = dist.get(state, INF)
            if f - h(r, c) > d + 0.01:
                continue
            if (r, c) == tgt:
                path = []
                s = state
                while s is not None:
                    path.append((s[0], s[1]))
                    s = parent.get(s)
                path.reverse()
                return path, d

            for new_di, (dr, dc) in enumerate(DIRS):
                nr, nc = r + dr, c + dc
                if not self.grid.in_bounds(nr, nc) or (nr, nc) in blocked:
                    continue
                ec = cost_fn(nr, nc) if cost_fn else 1.0
                if ec >= 1e20:
                    continue
                tc = turn_cost if (di != 4 and new_di != di) else 0.0
                nd = d + ec + tc
                new_state = (nr, nc, new_di)
                if nd < dist.get(new_state, INF):
                    dist[new_state] = nd
                    parent[new_state] = state
                    heapq.heappush(heap, (nd + h(nr, nc), counter, new_state))
                    counter += 1

        return [], INF

    def route_all(self, nets):
        result = RouterResult(algorithm=self.name)
        committed = set()

        for i, net in enumerate(nets):
            blocked = self._prepare_blocked(nets, i, committed)

            if i == 0:
                path = self._bfs(net["source"], net["target"], blocked)
                cost = float(len(path))
            else:
                cost_field = self._build_cost_field(committed, blocked)
                spacing_blocked = set(blocked)
                if committed:
                    sdist = self._build_distance_field(committed, blocked, self.spacing)
                    for cell, d in sdist.items():
                        if 0 < d <= self.spacing:
                            spacing_blocked.add(cell)
                spacing_blocked.discard(tuple(net["source"]))
                spacing_blocked.discard(tuple(net["target"]))

                def cost_fn(r, c):
                    if (r, c) in spacing_blocked:
                        return 1e30
                    return cost_field.get((r, c), 1.0)

                path, cost = self._astar_with_turns(
                    net["source"], net["target"],
                    spacing_blocked, cost_fn, self.turn_cost
                )
                # Fallback: if turn-aware routing fails, try without turn cost
                if not path:
                    path, cost = self._astar(net["source"], net["target"],
                                             spacing_blocked, cost_fn=cost_fn)
                # Last resort: plain BFS ignoring spacing
                if not path:
                    path = self._bfs(net["source"], net["target"], blocked)
                    cost = float(len(path))

            nr = NetResult(
                net_name=net.get("name", f"net{i}"),
                source=tuple(net["source"]),
                target=tuple(net["target"]),
                success=len(path) > 0,
                path=path, cost=cost,
            )
            result.nets.append(nr)
            if nr.success:
                committed.update(path)

        return result


# ════════════════════════════════════════════════════════════════
# 8. HYBRID RIP-UP + BUNDLE
# ════════════════════════════════════════════════════════════════

class HybridRipUpBundle(BaseRouter):
    """
    Rip-up-and-reroute with Bundle attraction during re-routing.
    Pass 1: Sequential BFS (fast initial solution).
    Pass 2+: Failed nets trigger rip-up. Rerouting uses cost-field
    attraction toward surviving routes — combining Rip-Up's conflict
    resolution with Bundle's compactness.
    """

    name = "Hybrid Rip+Bundle"

    def __init__(self, grid, max_passes=8, spacing=1, sweet_spot=2,
                 attract_cost=0.3, falloff=0.4, stray_cost=4.0,
                 turn_cost=0.3):
        super().__init__(grid)
        self.max_passes = max_passes
        self.spacing = spacing
        self.sweet_spot = sweet_spot
        self.attract_cost = attract_cost
        self.falloff = falloff
        self.stray_cost = stray_cost
        self.turn_cost = turn_cost

    def _cost_field_fn(self, committed, blocked):
        """Build a cost function from committed routes."""
        if not committed:
            return lambda r, c: 1.0

        dist = self._build_distance_field(
            committed, blocked,
            max_radius=self.sweet_spot + int(self.stray_cost / max(self.falloff, 0.01)) + 2
        )
        spacing_set = set()
        for cell, d in dist.items():
            if 0 < d <= self.spacing:
                spacing_set.add(cell)

        def fn(r, c):
            if (r, c) in blocked or (r, c) in spacing_set:
                return 1e30
            d = dist.get((r, c))
            if d is None:
                return 1.0
            if d == 0 or d <= self.spacing:
                return 1e30
            if d == self.sweet_spot:
                return self.attract_cost
            if d < self.sweet_spot:
                t = (d - self.spacing) / max(self.sweet_spot - self.spacing, 1)
                return 1.0 + t * (self.attract_cost - 1.0)
            return min(self.attract_cost + (d - self.sweet_spot) * self.falloff,
                       self.stray_cost)
        return fn

    def route_all(self, nets):
        result = RouterResult(algorithm=self.name)
        n = len(nets)
        paths = [[] for _ in range(n)]
        rip_count = [0] * n

        # Pass 1: sequential BFS
        committed = set()
        for i, net in enumerate(nets):
            blocked = self._prepare_blocked(nets, i, committed)
            paths[i] = self._bfs(net["source"], net["target"], blocked)
            if paths[i]:
                committed.update(paths[i])

        total_iters = 1

        for pass_num in range(1, self.max_passes):
            failed = [i for i in range(n) if not paths[i]]
            if not failed:
                break

            improved = False
            for fi in failed:
                fnet = nets[fi]
                fsrc, ftgt = tuple(fnet["source"]), tuple(fnet["target"])

                best_rip = None
                best_rip_cost = float('inf')

                for ri in range(n):
                    if ri == fi or not paths[ri]:
                        continue
                    rip_cost = len(paths[ri]) * (1 + rip_count[ri])
                    test_committed = set()
                    for j in range(n):
                        if j == ri or j == fi:
                            continue
                        test_committed.update(paths[j])
                    blocked = self._prepare_blocked(nets, fi, test_committed)
                    test_path = self._bfs(fnet["source"], fnet["target"], blocked)
                    if test_path and rip_cost < best_rip_cost:
                        best_rip = ri
                        best_rip_cost = rip_cost

                if best_rip is not None:
                    rip_count[best_rip] += 1
                    paths[best_rip] = []

                    # Rebuild committed (without ripped + failed nets)
                    committed = set()
                    for j in range(n):
                        committed.update(paths[j])

                    # Route failed net WITH bundle attraction
                    blocked_fi = self._prepare_blocked(nets, fi, committed)
                    cost_fn = self._cost_field_fn(committed, blocked_fi)
                    path_fi, _ = self._astar(fsrc, ftgt, blocked_fi, cost_fn=cost_fn)
                    if not path_fi:
                        path_fi = self._bfs(fnet["source"], fnet["target"], blocked_fi)
                    paths[fi] = path_fi
                    if path_fi:
                        committed.update(path_fi)

                    # Reroute ripped net WITH bundle attraction
                    rnet = nets[best_rip]
                    blocked_ri = self._prepare_blocked(nets, best_rip, committed)
                    cost_fn2 = self._cost_field_fn(committed, blocked_ri)
                    path_ri, _ = self._astar(
                        rnet["source"], rnet["target"], blocked_ri, cost_fn=cost_fn2
                    )
                    if not path_ri:
                        path_ri = self._bfs(rnet["source"], rnet["target"], blocked_ri)
                    paths[best_rip] = path_ri
                    if path_ri:
                        committed.update(path_ri)

                    improved = True

            total_iters += 1
            if not improved:
                break

        result.iterations = total_iters
        for i, net in enumerate(nets):
            nr = NetResult(
                net_name=net.get("name", f"net{i}"),
                source=tuple(net["source"]),
                target=tuple(net["target"]),
                success=len(paths[i]) > 0,
                path=paths[i],
                cost=float(len(paths[i])),
            )
            result.nets.append(nr)

        return result


# ════════════════════════════════════════════════════════════════
# 9. CORRIDOR ROUTER (topology-aware gap pre-assignment)
# ════════════════════════════════════════════════════════════════

class CorridorRouter(BaseRouter):
    """
    Pre-analyzes obstacle topology, assigns nets to corridors
    (which gap each net should use), then routes with waypoint
    bias toward assigned corridors.

    Steps:
    1. Scan for wall segments and identify gaps
    2. For each net, determine which walls must be crossed
    3. Assign each net to its nearest gap, spreading nets across gaps
    4. Route via A* with waypoint-attraction cost field
    """

    name = "Corridor Router"

    def __init__(self, grid, waypoint_pull=0.12, turn_cost=0.25):
        super().__init__(grid)
        self.waypoint_pull = waypoint_pull
        self.turn_cost = turn_cost

    def _find_walls_and_gaps(self):
        """Scan obstacles for horizontal/vertical wall segments and their gaps.

        Gaps include:
          - edge gaps: free range between grid edge and first wall end
          - inter-wall gaps: free range between two wall ends on the same row/col
        """
        obs = self.grid.obstacles
        walls = []  # {ori, coord, start, end}
        gaps = []   # {wall, ori, coord, range, mid, side}

        # Find horizontal walls (consecutive obstacles in same row)
        rows_walls = {}  # row -> list of wall indices, sorted by start
        for r in range(self.grid.rows):
            seg_start = None
            row_wall_ids = []
            for c in range(self.grid.cols + 1):
                is_obs = (r, c) in obs and c < self.grid.cols
                if is_obs and seg_start is None:
                    seg_start = c
                if not is_obs and seg_start is not None:
                    if c - seg_start >= 3:
                        wi = len(walls)
                        walls.append({'ori': 'H', 'coord': r, 'start': seg_start, 'end': c - 1})
                        row_wall_ids.append(wi)
                    seg_start = None
            if row_wall_ids:
                rows_walls[r] = row_wall_ids

        # Find vertical walls
        cols_walls = {}  # col -> list of wall indices, sorted by start
        for c in range(self.grid.cols):
            seg_start = None
            col_wall_ids = []
            for r in range(self.grid.rows + 1):
                is_obs = (r, c) in obs and r < self.grid.rows
                if is_obs and seg_start is None:
                    seg_start = r
                if not is_obs and seg_start is not None:
                    if r - seg_start >= 3:
                        wi = len(walls)
                        walls.append({'ori': 'V', 'coord': c, 'start': seg_start, 'end': r - 1})
                        col_wall_ids.append(wi)
                    seg_start = None
            if col_wall_ids:
                cols_walls[c] = col_wall_ids

        # Edge gaps for each wall
        for wi, w in enumerate(walls):
            if w['ori'] == 'H':
                if w['start'] > 0:
                    mid = w['start'] // 2
                    gaps.append({'wall': wi, 'ori': 'H', 'coord': w['coord'],
                                 'range': (0, w['start'] - 1),
                                 'mid': (w['coord'], mid), 'side': 'left'})
                if w['end'] < self.grid.cols - 1:
                    mid = (w['end'] + 1 + self.grid.cols) // 2
                    gaps.append({'wall': wi, 'ori': 'H', 'coord': w['coord'],
                                 'range': (w['end'] + 1, self.grid.cols - 1),
                                 'mid': (w['coord'], mid), 'side': 'right'})
            elif w['ori'] == 'V':
                if w['start'] > 0:
                    mid = w['start'] // 2
                    gaps.append({'wall': wi, 'ori': 'V', 'coord': w['coord'],
                                 'range': (0, w['start'] - 1),
                                 'mid': (mid, w['coord']), 'side': 'above'})
                if w['end'] < self.grid.rows - 1:
                    mid = (w['end'] + 1 + self.grid.rows) // 2
                    gaps.append({'wall': wi, 'ori': 'V', 'coord': w['coord'],
                                 'range': (w['end'] + 1, self.grid.rows - 1),
                                 'mid': (mid, w['coord']), 'side': 'below'})

        # Inter-wall gaps on same row (H-walls) / same col (V-walls).
        # A net crossing either adjacent wall can use this gap, so we record
        # the gap against BOTH walls.
        for r, wids in rows_walls.items():
            wids_sorted = sorted(wids, key=lambda i: walls[i]['start'])
            for a, b in zip(wids_sorted, wids_sorted[1:]):
                left_end = walls[a]['end']
                right_start = walls[b]['start']
                if right_start - left_end > 1:
                    mid_c = (left_end + right_start) // 2
                    gap = {'ori': 'H', 'coord': r,
                           'range': (left_end + 1, right_start - 1),
                           'mid': (r, mid_c), 'side': 'between'}
                    gaps.append({**gap, 'wall': a})
                    gaps.append({**gap, 'wall': b})

        for c, wids in cols_walls.items():
            wids_sorted = sorted(wids, key=lambda i: walls[i]['start'])
            for a, b in zip(wids_sorted, wids_sorted[1:]):
                top_end = walls[a]['end']
                bot_start = walls[b]['start']
                if bot_start - top_end > 1:
                    mid_r = (top_end + bot_start) // 2
                    gap = {'ori': 'V', 'coord': c,
                           'range': (top_end + 1, bot_start - 1),
                           'mid': (mid_r, c), 'side': 'between'}
                    gaps.append({**gap, 'wall': a})
                    gaps.append({**gap, 'wall': b})

        return walls, gaps

    def _assign_corridors(self, nets, walls, gaps):
        """Assign each net to specific gaps based on source/target positions."""
        waypoints = {}  # net_idx -> [(r, c), ...]

        for i, net in enumerate(nets):
            sr, sc = net["source"]
            tr, tc = net["target"]
            wps = []

            for wi, w in enumerate(walls):
                needs_cross = False
                if w['ori'] == 'H':
                    needs_cross = (sr < w['coord'] and tr > w['coord']) or \
                                  (sr > w['coord'] and tr < w['coord'])
                elif w['ori'] == 'V':
                    needs_cross = (sc < w['coord'] and tc > w['coord']) or \
                                  (sc > w['coord'] and tc < w['coord'])

                if needs_cross:
                    # Find best gap for this net
                    relevant_gaps = [g for g in gaps if g['wall'] == wi]
                    if not relevant_gaps:
                        continue

                    # Score by proximity to net's ideal crossing point
                    ideal_r = (sr + tr) // 2
                    ideal_c = (sc + tc) // 2

                    best_gap = min(relevant_gaps,
                                   key=lambda g: abs(g['mid'][0] - ideal_r) + abs(g['mid'][1] - ideal_c))

                    # Offset waypoint by lane index for parallel spacing
                    wr, wc = best_gap['mid']
                    if best_gap['ori'] == 'V':
                        wr = min(max(wr + i * 2, 0), self.grid.rows - 1)
                    else:
                        wc = min(max(wc + i * 2, 0), self.grid.cols - 1)
                    wps.append((wr, wc))

            waypoints[i] = wps

        return waypoints

    def _build_waypoint_cost(self, waypoints_for_net, blocked):
        """Build cost function that attracts toward waypoints."""
        if not waypoints_for_net:
            return None

        wp_set = set()
        for r, c in waypoints_for_net:
            if self.grid.in_bounds(r, c):
                wp_set.add((r, c))

        if not wp_set:
            return None

        wp_dist = self._build_distance_field(wp_set, self.grid.obstacles, max_radius=20)
        pull = self.waypoint_pull

        def cost_fn(r, c):
            if (r, c) in blocked:
                return 1e30
            d = wp_dist.get((r, c))
            if d is not None and d < 20:
                return max(0.3, 1.0 - pull * (20 - d))
            return 1.0

        return cost_fn

    def route_all(self, nets):
        result = RouterResult(algorithm=self.name)

        walls, gaps = self._find_walls_and_gaps()
        waypoints = self._assign_corridors(nets, walls, gaps)

        committed = set()
        for i, net in enumerate(nets):
            blocked = self._prepare_blocked(nets, i, committed)

            cost_fn = self._build_waypoint_cost(waypoints.get(i, []), blocked)
            if cost_fn:
                path, cost = self._astar(net["source"], net["target"],
                                         blocked, cost_fn=cost_fn)
            else:
                path = self._bfs(net["source"], net["target"], blocked)
                cost = float(len(path))

            nr = NetResult(
                net_name=net.get("name", f"net{i}"),
                source=tuple(net["source"]),
                target=tuple(net["target"]),
                success=len(path) > 0,
                path=path, cost=cost,
            )
            result.nets.append(nr)
            if nr.success:
                committed.update(path)

        return result


# ════════════════════════════════════════════════════════════════
# COMPARISON UTILITY
# ════════════════════════════════════════════════════════════════

def compare_routers(grid: Grid, nets: list[dict],
                    router_classes: list[type] = None,
                    **kwargs) -> dict[str, RouterResult]:
    """Run all router classes on the same grid/nets and compare."""
    import time

    if router_classes is None:
        router_classes = [
            SequentialBFS, AStarRouter, BundleRouter,
            RiverRouter, NegotiationRouter, RipUpRouter,
            SmoothBundleRouter, HybridRipUpBundle, CorridorRouter,
        ]

    results = {}
    for cls in router_classes:
        router = cls(grid, **{k: v for k, v in kwargs.items()
                              if k in cls.__init__.__code__.co_varnames})
        t0 = time.perf_counter()
        res = router.route_all(nets)
        res.time_ms = (time.perf_counter() - t0) * 1000
        results[cls.name] = res

    return results


# ════════════════════════════════════════════════════════════════
# DEMO
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    grid = Grid(50, 80)

    # Horizontal wall with gaps
    for c in range(10, 38):
        grid.add_obstacle(25, c)
    for c in range(42, 70):
        grid.add_obstacle(25, c)

    # Vertical wall
    for r in range(5, 42):
        grid.add_obstacle(r, 50)

    nets = [
        {"name": "D0", "source": (5, 0),  "target": (5, 79),  "source_dir": "E", "target_dir": "W"},
        {"name": "D1", "source": (12, 0), "target": (12, 79), "source_dir": "E", "target_dir": "W"},
        {"name": "D2", "source": (20, 0), "target": (20, 79), "source_dir": "E", "target_dir": "W"},
        {"name": "D3", "source": (35, 0), "target": (35, 79), "source_dir": "E", "target_dir": "W"},
        {"name": "D4", "source": (44, 0), "target": (44, 79), "source_dir": "E", "target_dir": "W"},
    ]

    print("=" * 70)
    print("ROUTING ALGORITHM COMPARISON")
    print("  Pin constraints: all sources exit EAST, all targets enter from WEST")
    print("=" * 70)
    print(f"Grid: {grid.rows}x{grid.cols}, Obstacles: {len(grid.obstacles)}")
    print(f"Nets: {len(nets)}")
    print()

    results = compare_routers(grid, nets)
    for name, res in results.items():
        print(f"  {res.summary()}  [{res.time_ms:.1f}ms]")
        for nr in res.nets:
            s = "✓" if nr.success else "✗"
            # Check direction compliance
            dir_ok = ""
            if nr.success and len(nr.path) >= 2:
                net = nets[res.nets.index(nr)] if nr in res.nets else None
                first_dr = nr.path[1][0] - nr.path[0][0]
                first_dc = nr.path[1][1] - nr.path[0][1]
                first_dir = DIR_NAMES.get((first_dr, first_dc), '?')
                last_dr = nr.path[-1][0] - nr.path[-2][0]
                last_dc = nr.path[-1][1] - nr.path[-2][1]
                approach_dir = DIR_NAMES.get((-last_dr, -last_dc), '?')
                dir_ok = f" exit={first_dir} enter={approach_dir}"
            print(f"    {s} {nr.net_name}: len={nr.length}{dir_ok}")
        print()
