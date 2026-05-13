"""
maze_router.py — Lee's Algorithm + Weighted Dijkstra Maze Router

Supports:
  - BFS shortest-path routing (Lee's Algorithm)
  - Dijkstra weighted routing with configurable cost fields
  - Bus/bundled routing: nets attract each other to run parallel
  - Multi-net sequential routing with net-ordering
  - Rip-up and reroute
  - Step-by-step iteration for visualization

Usage:
    from maze_router import MazeRouter, BundleRouter

    # === Standard multi-net routing ===
    router = MazeRouter(30, 40)
    router.add_obstacles([(10, c) for c in range(5, 20)])
    results = router.route_all([
        {"name": "CLK",  "source": (2, 3),  "target": (25, 35)},
        {"name": "DATA", "source": (5, 1),  "target": (20, 38)},
    ])

    # === Bundled bus routing (nets run parallel) ===
    bundle = BundleRouter(30, 40)
    bundle.add_obstacles([(15, c) for c in range(5, 35)])
    results = bundle.route_bus([
        {"name": "D0", "source": (3, 2),  "target": (27, 37)},
        {"name": "D1", "source": (4, 2),  "target": (27, 38)},
        {"name": "D2", "source": (5, 2),  "target": (27, 39)},
        {"name": "D3", "source": (6, 2),  "target": (27, 40)},
    ])
"""

from __future__ import annotations
import heapq
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


# ════════════════════════════════════════════════════════════════
# DATA TYPES
# ════════════════════════════════════════════════════════════════

class CellType(IntEnum):
    EMPTY = 0
    OBSTACLE = -1
    SOURCE = -2
    TARGET = -3


@dataclass
class RouteResult:
    net_name: str
    source: tuple[int, int]
    target: tuple[int, int]
    success: bool
    path: list[tuple[int, int]] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.path)


@dataclass
class ExpansionState:
    step: int
    frontier: list[tuple[int, int]]
    phase: str


@dataclass
class BacktraceState:
    step: int
    cell: tuple[int, int]
    phase: str


# ════════════════════════════════════════════════════════════════
# COST FIELD — generates weighted cost maps for Dijkstra routing
# ════════════════════════════════════════════════════════════════

class CostField:
    """
    Generates a 2D cost map based on proximity to existing routed paths.

    The cost model for bundled/bus routing:
      - Cells ON a routed path       -> blocked (infinite cost)
      - Cells within `spacing` dist  -> blocked (no-touch rule)
      - Cells at `sweet_spot` dist   -> minimum cost (attraction)
      - Cells farther away           -> increasing cost (penalty for straying)

    Parameters:
        base_cost:    default cost for cells with no nearby routes (first net)
        attract_cost: minimum cost at the sweet spot distance
        spacing:      minimum distance from existing routes (blocked)
        sweet_spot:   ideal parallel distance (lowest cost)
        falloff:      how fast cost increases beyond sweet spot
        stray_cost:   maximum cost for cells far from any route
    """

    def __init__(
        self,
        base_cost: float = 1.0,
        attract_cost: float = 0.2,
        spacing: int = 1,
        sweet_spot: int = 2,
        falloff: float = 0.5,
        stray_cost: float = 5.0,
    ):
        self.base_cost = base_cost
        self.attract_cost = attract_cost
        self.spacing = spacing
        self.sweet_spot = sweet_spot
        self.falloff = falloff
        self.stray_cost = stray_cost

    def build_cost_grid(
        self,
        rows: int,
        cols: int,
        grid: list[list[int]],
        net_map: dict[tuple[int, int], str],
    ) -> list[list[float]]:
        """
        Build a cost grid based on current routing state.

        Returns a 2D array where:
          - float('inf') = blocked
          - low values = attractive (near existing routes)
          - high values = penalty (far from routes)
        """
        INF = float('inf')
        cost = [[self.base_cost] * cols for _ in range(rows)]

        # Mark obstacles as blocked
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == CellType.OBSTACLE:
                    cost[r][c] = INF

        # If no routes exist yet, return uniform base cost
        if not net_map:
            return cost

        # BFS from all routed path cells to compute distance field
        dist = [[INF] * cols for _ in range(rows)]
        queue = deque()

        for (r, c) in net_map:
            dist[r][c] = 0
            queue.append((r, c))

        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        max_radius = self.sweet_spot + int(self.stray_cost / max(self.falloff, 0.01)) + 2

        while queue:
            r, c = queue.popleft()
            if dist[r][c] >= max_radius:
                continue
            for dr, dc in dirs:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    nd = dist[r][c] + 1
                    if nd < dist[nr][nc]:
                        dist[nr][nc] = nd
                        queue.append((nr, nc))

        # Map distances to costs
        for r in range(rows):
            for c in range(cols):
                if cost[r][c] == INF:
                    continue  # already blocked

                d = dist[r][c]

                if d == 0:
                    cost[r][c] = INF
                elif d <= self.spacing:
                    cost[r][c] = INF
                elif d == self.sweet_spot:
                    cost[r][c] = self.attract_cost
                elif d < self.sweet_spot:
                    t = (d - self.spacing) / max(self.sweet_spot - self.spacing, 1)
                    cost[r][c] = self.base_cost + t * (self.attract_cost - self.base_cost)
                else:
                    overshoot = d - self.sweet_spot
                    cost[r][c] = self.attract_cost + overshoot * self.falloff
                    cost[r][c] = min(cost[r][c], self.stray_cost)

        return cost


# ════════════════════════════════════════════════════════════════
# MAZE ROUTER — BFS (Lee's Algorithm)
# ════════════════════════════════════════════════════════════════

class MazeRouter:
    DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self.grid: list[list[int]] = [[0] * cols for _ in range(rows)]
        self.routed_nets: list[RouteResult] = []
        self._net_map: dict[tuple[int, int], str] = {}

    def in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols

    def add_obstacle(self, r, c):
        if self.in_bounds(r, c): self.grid[r][c] = CellType.OBSTACLE

    def add_obstacles(self, cells):
        for r, c in cells: self.add_obstacle(r, c)

    def clear_cell(self, r, c):
        if self.in_bounds(r, c):
            self.grid[r][c] = CellType.EMPTY
            self._net_map.pop((r, c), None)

    def reset_grid(self):
        self.grid = [[0] * self.cols for _ in range(self.rows)]
        self.routed_nets.clear()
        self._net_map.clear()

    def _clear_bfs_labels(self):
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] > 0: self.grid[r][c] = CellType.EMPTY

    def route(self, source, target, net_name="net0", commit=True):
        path, stats = self._run_bfs(source, target)
        result = RouteResult(net_name=net_name, source=source, target=target,
                             success=len(path) > 0, path=path, stats=stats)
        if commit:
            if result.success: self._commit_path(path, net_name)
            self.routed_nets.append(result)
        self._clear_bfs_labels()
        return result

    def _run_bfs(self, source, target):
        sr, sc = source; tr, tc = target
        if not self.in_bounds(sr, sc) or not self.in_bounds(tr, tc):
            return [], {"error": "out_of_bounds"}
        if self.grid[sr][sc] == CellType.OBSTACLE or self.grid[tr][tc] == CellType.OBSTACLE:
            return [], {"error": "pin_on_obstacle"}
        parent = {source: None}; queue = deque([source])
        cells_visited = 0; expansion_steps = 0; found = False
        while queue and not found:
            expansion_steps += 1; next_queue = []
            while queue:
                r, c = queue.popleft(); cells_visited += 1
                for dr, dc in self.DIRS:
                    nr, nc = r + dr, c + dc
                    if not self.in_bounds(nr, nc) or (nr, nc) in parent: continue
                    if self.grid[nr][nc] == CellType.OBSTACLE: continue
                    parent[(nr, nc)] = (r, c)
                    if (nr, nc) == target: found = True; break
                    self.grid[nr][nc] = expansion_steps
                    next_queue.append((nr, nc))
                if found: break
            queue = deque(next_queue)
        stats = {"cells_visited": cells_visited, "expansion_steps": expansion_steps, "found": found}
        if not found: return [], stats
        path = []; cell = target
        while cell is not None: path.append(cell); cell = parent[cell]
        path.reverse(); stats["path_length"] = len(path)
        return path, stats

    def _commit_path(self, path, net_name):
        for r, c in path:
            self.grid[r][c] = CellType.OBSTACLE
            self._net_map[(r, c)] = net_name

    def route_all(self, nets, order=None):
        """Route multiple nets with pin reservation to prevent path-through-pin conflicts."""
        if order is None: order = list(range(len(nets)))

        # Collect all pins
        all_pins = set()
        for net in nets:
            all_pins.add(tuple(net["source"]))
            all_pins.add(tuple(net["target"]))

        # Reserve all pins as obstacles
        for r, c in all_pins:
            if self.in_bounds(r, c) and self.grid[r][c] == CellType.EMPTY:
                self.grid[r][c] = CellType.OBSTACLE

        results = []
        for idx in order:
            net = nets[idx]
            src, tgt = tuple(net["source"]), tuple(net["target"])

            # Temporarily unblock this net's own pins
            self.grid[src[0]][src[1]] = CellType.EMPTY
            self.grid[tgt[0]][tgt[1]] = CellType.EMPTY

            result = self.route(src, tgt, net.get("name", f"net{idx}"), commit=True)
            results.append(result)

            # If routing failed, re-reserve pins for future nets
            if not result.success:
                self.grid[src[0]][src[1]] = CellType.OBSTACLE
                self.grid[tgt[0]][tgt[1]] = CellType.OBSTACLE

        return results

    def rip_up_and_reroute(self, nets, new_order):
        for (r, c) in list(self._net_map.keys()): self.grid[r][c] = CellType.EMPTY
        self._net_map.clear(); self.routed_nets.clear(); self._clear_bfs_labels()
        return self.route_all(nets, order=new_order)

    def summary(self):
        total = sum(r.length for r in self.routed_nets if r.success)
        ok = sum(1 for r in self.routed_nets if r.success)
        lines = [f"MazeRouter {self.rows}x{self.cols} — {ok}/{len(self.routed_nets)} nets, wirelength={total}"]
        for r in self.routed_nets:
            s = "✓" if r.success else "✗"
            lines.append(f"  {s} {r.net_name}: {r.source}→{r.target}, len={r.length}")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# BUNDLE ROUTER — Dijkstra with cost-field attraction
# ════════════════════════════════════════════════════════════════

class BundleRouter:
    """
    Weighted Dijkstra router that attracts nets to run parallel.
    First net routes via BFS (shortest path), subsequent nets
    use a cost field that pulls them toward the existing bundle.
    """
    DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def __init__(self, rows, cols, cost_field=None):
        self.rows = rows
        self.cols = cols
        self.grid = [[0] * cols for _ in range(rows)]
        self.routed_nets: list[RouteResult] = []
        self._net_map: dict[tuple[int, int], str] = {}
        self.cost_field = cost_field or CostField()
        self._last_cost_grid = None

    def in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols

    def add_obstacle(self, r, c):
        if self.in_bounds(r, c): self.grid[r][c] = CellType.OBSTACLE

    def add_obstacles(self, cells):
        for r, c in cells: self.add_obstacle(r, c)

    def clear_cell(self, r, c):
        if self.in_bounds(r, c):
            self.grid[r][c] = CellType.EMPTY
            self._net_map.pop((r, c), None)

    def reset_grid(self):
        self.grid = [[0] * self.cols for _ in range(self.rows)]
        self.routed_nets.clear(); self._net_map.clear(); self._last_cost_grid = None

    def _commit_path(self, path, net_name):
        for r, c in path:
            self.grid[r][c] = CellType.OBSTACLE
            self._net_map[(r, c)] = net_name

    def get_cost_grid(self):
        """Build and return the current cost landscape."""
        self._last_cost_grid = self.cost_field.build_cost_grid(
            self.rows, self.cols, self.grid, self._net_map)
        return self._last_cost_grid

    def route_dijkstra(self, source, target, net_name="net0", commit=True):
        cost_grid = self.get_cost_grid()
        # Exempt source and target from blocking — they must be reachable
        sr, sc = source; tr, tc = target
        if self.in_bounds(sr, sc): cost_grid[sr][sc] = 0.0
        if self.in_bounds(tr, tc): cost_grid[tr][tc] = 0.0
        path, stats = self._run_dijkstra(source, target, cost_grid)
        result = RouteResult(net_name=net_name, source=source, target=target,
                             success=len(path) > 0, path=path, stats=stats)
        if commit and result.success:
            self._commit_path(path, net_name)
        self.routed_nets.append(result)
        return result

    def _run_dijkstra(self, source, target, cost_grid):
        sr, sc = source; tr, tc = target
        INF = float('inf')
        if not self.in_bounds(sr, sc) or not self.in_bounds(tr, tc):
            return [], {"error": "out_of_bounds"}
        if cost_grid[sr][sc] == INF or cost_grid[tr][tc] == INF:
            return [], {"error": "pin_blocked"}

        dist = [[INF] * self.cols for _ in range(self.rows)]
        dist[sr][sc] = 0.0
        parent = {source: None}
        heap = [(0.0, sr, sc)]
        cells_visited = 0

        while heap:
            d, r, c = heapq.heappop(heap)
            if d > dist[r][c]: continue
            cells_visited += 1
            if (r, c) == target: break
            for dr, dc in self.DIRS:
                nr, nc = r + dr, c + dc
                if not self.in_bounds(nr, nc): continue
                cell_cost = cost_grid[nr][nc]
                if cell_cost == INF: continue
                nd = d + cell_cost
                if nd < dist[nr][nc]:
                    dist[nr][nc] = nd
                    parent[(nr, nc)] = (r, c)
                    heapq.heappush(heap, (nd, nr, nc))

        stats = {"cells_visited": cells_visited, "found": dist[tr][tc] < INF}
        if dist[tr][tc] == INF: return [], stats
        stats["total_cost"] = round(dist[tr][tc], 2)
        path = []; cell = target
        while cell is not None: path.append(cell); cell = parent.get(cell)
        path.reverse(); stats["path_length"] = len(path)
        return path, stats

    def _run_bfs(self, source, target):
        sr, sc = source; tr, tc = target
        if not self.in_bounds(sr, sc) or not self.in_bounds(tr, tc):
            return [], {"error": "out_of_bounds"}
        if self.grid[sr][sc] == CellType.OBSTACLE or self.grid[tr][tc] == CellType.OBSTACLE:
            return [], {"error": "pin_on_obstacle"}
        parent = {source: None}; queue = deque([source])
        cells_visited = 0; found = False
        while queue and not found:
            r, c = queue.popleft(); cells_visited += 1
            for dr, dc in self.DIRS:
                nr, nc = r + dr, c + dc
                if not self.in_bounds(nr, nc) or (nr, nc) in parent: continue
                if self.grid[nr][nc] == CellType.OBSTACLE: continue
                parent[(nr, nc)] = (r, c)
                if (nr, nc) == target: found = True; break
                queue.append((nr, nc))
        stats = {"cells_visited": cells_visited, "found": found}
        if not found: return [], stats
        path = []; cell = target
        while cell is not None: path.append(cell); cell = parent[cell]
        path.reverse(); stats["path_length"] = len(path)
        return path, stats

    def route_bus(self, nets, order=None):
        """Route a bus with pin reservation: first net BFS, rest Dijkstra with attraction."""
        if order is None: order = list(range(len(nets)))

        # Reserve all pins
        all_pins = set()
        for net in nets:
            all_pins.add(tuple(net["source"]))
            all_pins.add(tuple(net["target"]))
        for r, c in all_pins:
            if self.in_bounds(r, c) and self.grid[r][c] == 0:
                self.grid[r][c] = CellType.OBSTACLE

        results = []
        for i, idx in enumerate(order):
            net = nets[idx]; name = net.get("name", f"net{idx}")
            src, tgt = tuple(net["source"]), tuple(net["target"])

            # Unblock this net's pins
            self.grid[src[0]][src[1]] = 0
            self.grid[tgt[0]][tgt[1]] = 0

            if i == 0:
                path, stats = self._run_bfs(src, tgt)
                result = RouteResult(net_name=name, source=src,
                    target=tgt, success=len(path) > 0, path=path, stats=stats)
                if result.success: self._commit_path(path, name)
                self.routed_nets.append(result)
            else:
                result = self.route_dijkstra(src, tgt, name)
            results.append(result)

            # Re-reserve if failed
            if not result.success:
                self.grid[src[0]][src[1]] = CellType.OBSTACLE
                self.grid[tgt[0]][tgt[1]] = CellType.OBSTACLE

        return results

    def iter_dijkstra(self, source, target, cost_grid=None):
        """Generator yielding per-cell Dijkstra expansion for visualization."""
        if cost_grid is None: cost_grid = self.get_cost_grid()
        sr, sc = source; tr, tc = target; INF = float('inf')
        dist = [[INF] * self.cols for _ in range(self.rows)]
        dist[sr][sc] = 0.0; parent = {source: None}
        heap = [(0.0, sr, sc)]; step = 0
        while heap:
            d, r, c = heapq.heappop(heap)
            if d > dist[r][c]: continue
            step += 1
            yield {"step": step, "cell": (r, c), "dist": d, "phase": "expanding"}
            if (r, c) == target:
                path = []; cell = target
                while cell is not None: path.append(cell); cell = parent.get(cell)
                path.reverse()
                for i, bc in enumerate(path):
                    yield {"step": i, "cell": bc,
                           "phase": "backtracing" if i < len(path) - 1 else "done"}
                return
            for dr, dc in self.DIRS:
                nr, nc = r + dr, c + dc
                if not self.in_bounds(nr, nc): continue
                cc = cost_grid[nr][nc]
                if cc == INF: continue
                nd = d + cc
                if nd < dist[nr][nc]:
                    dist[nr][nc] = nd; parent[(nr, nc)] = (r, c)
                    heapq.heappush(heap, (nd, nr, nc))
        yield {"step": step, "cell": source, "phase": "no_path"}

    def summary(self):
        total = sum(r.length for r in self.routed_nets if r.success)
        ok = sum(1 for r in self.routed_nets if r.success)
        lines = [f"BundleRouter {self.rows}x{self.cols} — {ok}/{len(self.routed_nets)} nets, wirelength={total}"]
        for r in self.routed_nets:
            s = "✓" if r.success else "✗"
            cost = r.stats.get("total_cost", "—")
            lines.append(f"  {s} {r.net_name}: {r.source}→{r.target}, len={r.length}, cost={cost}")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# DEMO
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("DEMO 1: Standard multi-net routing (BFS)")
    print("=" * 60)

    router = MazeRouter(20, 30)
    for c in range(4, 12): router.add_obstacle(10, c)
    for c in range(14, 25): router.add_obstacle(10, c)
    nets = [
        {"name": "CLK",  "source": (2, 3),   "target": (18, 27)},
        {"name": "DATA", "source": (3, 12),  "target": (17, 13)},
        {"name": "RST",  "source": (0, 20),  "target": (19, 20)},
    ]
    router.route_all(nets)
    print(router.summary())
    print()

    print("=" * 60)
    print("DEMO 2: Bundled bus routing vs BFS — no obstacles")
    print("=" * 60)

    bus_nets = [
        {"name": "D0", "source": (10, 0), "target": (10, 49)},
        {"name": "D1", "source": (14, 0), "target": (14, 49)},
        {"name": "D2", "source": (18, 0), "target": (18, 49)},
        {"name": "D3", "source": (22, 0), "target": (22, 49)},
    ]

    bundle = BundleRouter(30, 50)
    bundle.route_bus(bus_nets)
    print(bundle.summary())
    for r in bundle.routed_nets:
        if r.success:
            mid = len(r.path) // 2
            print(f"  → {r.net_name} midpoint row: {r.path[mid][0]}")

    print()
    router2 = MazeRouter(30, 50)
    router2.route_all(bus_nets)
    print(router2.summary())
    for r in router2.routed_nets:
        if r.success:
            mid = len(r.path) // 2
            print(f"  → {r.net_name} midpoint row: {r.path[mid][0]}")

    print()
    print("→ BFS: paths stay at rows 10,14,18,22 (scattered across 12 rows)")
    print("→ Bundle: paths pulled to rows 10,12,14,16 (compact 6-row bundle!)")
    print()

    print("=" * 60)
    print("DEMO 3: Bundled bus routing — with wall obstacle")
    print("=" * 60)

    bus_nets2 = [
        {"name": "D0", "source": (10, 0), "target": (10, 49)},
        {"name": "D1", "source": (12, 0), "target": (12, 49)},
        {"name": "D2", "source": (14, 0), "target": (14, 49)},
        {"name": "D3", "source": (16, 0), "target": (16, 49)},
    ]

    bundle2 = BundleRouter(30, 50)
    for r in range(5, 26): bundle2.add_obstacle(r, 25)
    bundle2.route_bus(bus_nets2)
    print(bundle2.summary())
    print("→ Watch them detour together around the wall as a bundle!")
