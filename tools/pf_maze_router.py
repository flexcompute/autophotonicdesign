"""
pf_maze_router.py — PhotonForge integration layer for the grid-based maze router.

Bridges between PhotonForge layout coordinates (continuous, in um) and the
integer-grid maze router. Handles:
  - Rasterizing PF structures on a given layer into grid obstacles
  - Converting terminal positions to grid coordinates
  - Running the maze router (BFS / Dijkstra)
  - Converting grid paths back to Manhattan waypoints
  - Creating PF route geometry via Path objects

Usage:
    import photonforge as pf
    from pf_maze_router import PFMazeRouter

    router = PFMazeRouter(component, layer="M2_router", grid_pitch=25)
    router.add_terminal_pair("T0_pad1", terminal1, "T0_pad2", terminal2)
    results = router.route_all(trace_width=25)
    # results is a list of PF Components containing the routes
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import photonforge as pf

from maze_router import MazeRouter, BundleRouter, CostField, RouteResult


# ════════════════════════════════════════════════════════════════
# COORDINATE MAPPING
# ════════════════════════════════════════════════════════════════

@dataclass
class GridMapping:
    """Maps between layout coordinates (um) and grid indices."""

    grid_pitch: float
    origin_x: float
    origin_y: float
    rows: int
    cols: int

    def layout_to_grid(self, x: float, y: float) -> tuple[int, int]:
        """Convert layout (x, y) to grid (row, col). Row = y-axis, Col = x-axis."""
        col = round((x - self.origin_x) / self.grid_pitch)
        row = round((y - self.origin_y) / self.grid_pitch)
        col = max(0, min(col, self.cols - 1))
        row = max(0, min(row, self.rows - 1))
        return (row, col)

    def grid_to_layout(self, row: int, col: int) -> tuple[float, float]:
        """Convert grid (row, col) to layout (x, y)."""
        x = self.origin_x + col * self.grid_pitch
        y = self.origin_y + row * self.grid_pitch
        return (x, y)


def compute_grid_mapping(
    bbox_min: tuple[float, float],
    bbox_max: tuple[float, float],
    grid_pitch: float,
    margin: int = 5,
) -> GridMapping:
    """Create a GridMapping that covers the given bounding box with margin cells."""
    origin_x = bbox_min[0] - margin * grid_pitch
    origin_y = bbox_min[1] - margin * grid_pitch
    cols = math.ceil((bbox_max[0] - origin_x) / grid_pitch) + margin + 1
    rows = math.ceil((bbox_max[1] - origin_y) / grid_pitch) + margin + 1
    return GridMapping(
        grid_pitch=grid_pitch,
        origin_x=origin_x,
        origin_y=origin_y,
        rows=rows,
        cols=cols,
    )


# ════════════════════════════════════════════════════════════════
# OBSTACLE RASTERIZATION
# ════════════════════════════════════════════════════════════════

def rasterize_bbox(
    gm: GridMapping,
    x_min: float, y_min: float,
    x_max: float, y_max: float,
    margin: int = 0,
) -> list[tuple[int, int]]:
    """Convert a layout bounding box to a list of occupied grid cells."""
    r_min, c_min = gm.layout_to_grid(x_min, y_min)
    r_max, c_max = gm.layout_to_grid(x_max, y_max)

    # Ensure min <= max
    r_min, r_max = min(r_min, r_max), max(r_min, r_max)
    c_min, c_max = min(c_min, c_max), max(c_min, c_max)

    # Apply margin
    r_min = max(0, r_min - margin)
    r_max = min(gm.rows - 1, r_max + margin)
    c_min = max(0, c_min - margin)
    c_max = min(gm.cols - 1, c_max + margin)

    cells = []
    for r in range(r_min, r_max + 1):
        for c in range(c_min, c_max + 1):
            cells.append((r, c))
    return cells


def rasterize_structures(
    gm: GridMapping,
    component: pf.Component,
    layer,
    margin: int = 0,
) -> list[tuple[int, int]]:
    """Rasterize all structures on `layer` in the component.

    IMPORTANT: component.flatten() mutates the component in place (wipes its
    references). Use get_structures(layer) instead, which walks references
    without modifying the component.
    """
    all_cells = []
    try:
        structs = component.get_structures(layer)
    except Exception:
        structs = []
    for s in structs:
        bb_min, bb_max = s.bounds()
        cells = rasterize_bbox(gm, bb_min[0], bb_min[1], bb_max[0], bb_max[1], margin)
        all_cells.extend(cells)
    return all_cells


def rasterize_structures_inflated(
    gm: GridMapping,
    component: pf.Component,
    layer,
    inflate_um: float = 0.0,
) -> list[tuple[int, int]]:
    """Rasterize structures on `layer` after INFLATING each polygon in layout
    coords by `inflate_um` µm. Use inflate_um = trace_width/2 + epsilon to
    guarantee that any grid cell whose center produces a trace that could
    touch the obstacle is blocked.

    This is geometrically correct in a way rasterize_structures (bbox+margin)
    isn't — narrow polygons inside a cell don't rely on margin rounding.
    """
    all_cells = set()
    try:
        structs = component.get_structures(layer)
    except Exception:
        return []
    # Inflate each structure in layout space using pf.offset (miter joins)
    for s in structs:
        try:
            inflated = pf.offset(s, inflate_um) if inflate_um > 0 else [s]
        except Exception:
            inflated = [s]
        # pf.offset can return a Polygon or a list; normalize
        if not isinstance(inflated, (list, tuple)):
            inflated = [inflated]
        for poly in inflated:
            try:
                bb_min, bb_max = poly.bounds()
            except Exception:
                continue
            # Iterate cells whose center is inside the polygon bbox
            cells = rasterize_bbox(gm, bb_min[0], bb_min[1], bb_max[0], bb_max[1], margin=0)
            for cell in cells:
                all_cells.add(cell)
    return list(all_cells)


# ════════════════════════════════════════════════════════════════
# PATH SIMPLIFICATION
# ════════════════════════════════════════════════════════════════

def simplify_grid_path(path: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Remove collinear interior points, keeping only corners + endpoints."""
    if len(path) <= 2:
        return list(path)

    simplified = [path[0]]
    for i in range(1, len(path) - 1):
        pr, pc = path[i - 1]
        cr, cc = path[i]
        nr, nc = path[i + 1]
        dr1, dc1 = cr - pr, cc - pc
        dr2, dc2 = nr - cr, nc - cc
        if (dr1, dc1) != (dr2, dc2):
            simplified.append(path[i])
    simplified.append(path[-1])
    return simplified


def smooth_corners(corners: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Remove staircase jogs from a Manhattan corner list.

    Dijkstra paths following a cost channel create staircases at turns:
        A → B → C → D  (alternating short H/V segments)
    This replaces them with a single L-turn: A → corner → D.

    Single pass: scan for runs of consecutive short (≤ 3 cell) alternating
    segments and collapse each run into one L-turn.
    """
    if len(corners) <= 3:
        return corners

    result = [corners[0]]
    i = 1
    while i < len(corners):
        # Try to find a staircase run starting at result[-1]→corners[i]
        run_start = len(result) - 1
        j = i
        while j < len(corners) - 1:
            prev = corners[j - 1] if j > i else result[-1]
            curr = corners[j]
            nxt = corners[j + 1]
            seg_len = abs(curr[0] - prev[0]) + abs(curr[1] - prev[1])
            nxt_len = abs(nxt[0] - curr[0]) + abs(nxt[1] - curr[1])
            h1 = (curr[0] == prev[0])
            h2 = (nxt[0] == curr[0])
            if seg_len <= 3 and nxt_len <= 3 and h1 != h2:
                j += 1
            else:
                break

        if j > i:
            # Found a staircase from result[-1] through corners[i..j-1] to corners[j]
            start_pt = result[-1]
            end_pt = corners[j]
            # Determine L-corner: continue start direction to meet end
            first_seg_horizontal = (corners[i][0] == start_pt[0])
            if first_seg_horizontal:
                lc = (start_pt[0], end_pt[1])
            else:
                lc = (end_pt[0], start_pt[1])
            if lc != start_pt and lc != end_pt:
                result.append(lc)
            result.append(end_pt)
            i = j + 1
        else:
            result.append(corners[i])
            i += 1

    return result


def grid_path_to_layout_waypoints(
    gm: GridMapping,
    grid_path: list[tuple[int, int]],
) -> list[tuple[float, float]]:
    """Convert a grid path to a list of layout waypoints (corners only, smoothed)."""
    corners = simplify_grid_path(grid_path)
    corners = smooth_corners(corners)
    return [gm.grid_to_layout(r, c) for r, c in corners]


# ════════════════════════════════════════════════════════════════
# PF MAZE ROUTER — Main integration class
# ════════════════════════════════════════════════════════════════

@dataclass
class TerminalPair:
    """A pair of terminals to route."""
    name: str
    terminal1: pf.Terminal
    terminal2: pf.Terminal


@dataclass
class PFRouteResult:
    """Result of routing one terminal pair."""
    name: str
    success: bool
    grid_result: RouteResult | None = None
    waypoints: list[tuple[float, float]] = field(default_factory=list)
    component: pf.Component | None = None


class PFMazeRouter:
    """
    Grid-based maze router for PhotonForge terminal routing.

    Workflow:
      1. Create router with a bounding box and grid pitch
      2. Add obstacles from layout geometry
      3. Add terminal pairs to route
      4. Route all pairs (BFS with obstacle avoidance)
      5. Get back PF Components with the routed paths
    """

    def __init__(
        self,
        bbox_min: tuple[float, float],
        bbox_max: tuple[float, float],
        grid_pitch: float,
        margin: int = 5,
    ):
        self.gm = compute_grid_mapping(bbox_min, bbox_max, grid_pitch, margin)
        self.router = MazeRouter(self.gm.rows, self.gm.cols)
        self.terminal_pairs: list[TerminalPair] = []
        self.results: list[PFRouteResult] = []
        self._obstacle_cells: set[tuple[int, int]] = set()

    @property
    def grid_pitch(self) -> float:
        return self.gm.grid_pitch

    def add_obstacles_from_layer(
        self,
        component: pf.Component,
        layer,
        margin: int = 0,
    ):
        """Rasterize all structures on a layer as obstacles.

        Can be called multiple times with different layers to build up
        the obstacle set from several mask layers.
        """
        cells = rasterize_structures(self.gm, component, layer, margin)
        self.router.add_obstacles(cells)
        self._obstacle_cells.update(cells)

    def add_obstacle_rect(
        self,
        x_min: float, y_min: float,
        x_max: float, y_max: float,
        margin: int = 0,
    ):
        """Add a rectangular obstacle region in layout coordinates."""
        cells = rasterize_bbox(self.gm, x_min, y_min, x_max, y_max, margin)
        self.router.add_obstacles(cells)
        self._obstacle_cells.update(cells)

    def add_terminal_pair(
        self,
        name: str,
        terminal1: pf.Terminal,
        terminal2: pf.Terminal,
    ):
        """Register a pair of terminals to route."""
        self.terminal_pairs.append(TerminalPair(name, terminal1, terminal2))

    def _get_terminal_footprint(
        self,
        terminal: pf.Terminal,
        margin: int = 0,
    ) -> list[tuple[int, int]]:
        """Get grid cells covered by a terminal's footprint (with margin)."""
        bb_min, bb_max = terminal.bounds()
        return rasterize_bbox(
            self.gm, bb_min[0], bb_min[1], bb_max[0], bb_max[1],
            margin=margin,
        )

    def route_all(
        self,
        trace_width: float,
        layer=None,
    ) -> list[PFRouteResult]:
        """
        Route all registered terminal pairs using BFS maze routing.

        Terminal pad areas are on the routing layer, so they show up as
        obstacles after rasterization. The routing loop handles this:

        For each net:
          1. Force-clear current net's pad interiors (so BFS can start/end)
          2. Force-clear a 1-cell exit border around current net's pads
             (so BFS can escape the pad area)
          3. Re-block other nets' pad interiors (so routes can't cut through)
          4. Run BFS
          5. Restore all temporary changes

        Args:
            trace_width: Width of the route traces in um.
            layer: PF layer for the route geometry. Defaults to terminal1's routing_layer.

        Returns:
            List of PFRouteResult, each containing the PF Component with the route.
        """
        # Pre-compute footprints for each terminal pair.
        # "pad" = actual pad area (margin=0) — must be passable for own net
        # "exit" = pad + 1-cell border (margin=1) — BFS needs an exit corridor
        net_infos = []
        for tp in self.terminal_pairs:
            c1 = tp.terminal1.center()
            c2 = tp.terminal2.center()
            src = self.gm.layout_to_grid(c1[0], c1[1])
            tgt = self.gm.layout_to_grid(c2[0], c2[1])
            pad1 = set(self._get_terminal_footprint(tp.terminal1, margin=0))
            pad2 = set(self._get_terminal_footprint(tp.terminal2, margin=0))
            exit1 = set(self._get_terminal_footprint(tp.terminal1, margin=1))
            exit2 = set(self._get_terminal_footprint(tp.terminal2, margin=1))
            net_infos.append({
                "name": tp.name, "source": src, "target": tgt,
                "pad1": pad1, "pad2": pad2,
                "exit1": exit1, "exit2": exit2,
            })

        # Collect all pad interiors (used to re-block other nets' pads)
        all_pads = set()
        for info in net_infos:
            all_pads.update(info["pad1"])
            all_pads.update(info["pad2"])

        # Route nets one at a time
        self.results = []
        for i, (tp, info) in enumerate(zip(self.terminal_pairs, net_infos)):
            route_layer = layer if layer is not None else tp.terminal1.routing_layer

            # Step 1: Force-clear this net's exit zones (pad + 1-cell border).
            # This removes ALL obstacles in the zone — layer obstacles, margins, etc.
            # We need this so BFS can start on the pad and exit through the border.
            my_exit = info["exit1"] | info["exit2"]
            for r, c in my_exit:
                self.router.clear_cell(r, c)

            # Step 2: Re-block other nets' full exit zones (interior + border).
            # We cleared a zone that might overlap with other pads' areas.
            # Block them back so this net can't route through them.
            other_exits = set()
            for j, other_info in enumerate(net_infos):
                if j != i:
                    other_exits.update(other_info["exit1"])
                    other_exits.update(other_info["exit2"])
            # Only re-block cells that we actually cleared
            reblock = other_exits & my_exit
            self.router.add_obstacles(list(reblock))

            # Step 3: Route
            result = self.router.route(
                info["source"], info["target"], info["name"], commit=True,
            )

            # Step 4: Restore — re-block all cleared cells that aren't on the path
            path_set = set(result.path) if result.success else set()
            for cell in my_exit:
                if cell not in path_set:
                    self.router.add_obstacle(*cell)

            if not result.success:
                self.results.append(PFRouteResult(
                    name=tp.name, success=False, grid_result=result,
                ))
                continue

            # Convert grid path to layout waypoints
            waypoints = grid_path_to_layout_waypoints(self.gm, result.path)

            comp = self._create_route_component(
                tp.name, waypoints, trace_width, route_layer,
            )

            self.results.append(PFRouteResult(
                name=tp.name,
                success=True,
                grid_result=result,
                waypoints=waypoints,
                component=comp,
            ))

        return self.results

    def _create_route_component(
        self,
        name: str,
        waypoints: list[tuple[float, float]],
        trace_width: float,
        layer,
    ) -> pf.Component:
        """Create a PF Component containing the Manhattan route path."""
        comp = pf.Component(f"maze_route_{name}")

        if len(waypoints) < 2:
            return comp

        start = waypoints[0]
        remaining = waypoints[1:]

        path = pf.Path(start, trace_width).segment(remaining)
        comp.add(layer, path)
        return comp

    def summary(self) -> str:
        """Print a summary of routing results."""
        lines = [
            f"PFMazeRouter: grid {self.gm.rows}x{self.gm.cols}, "
            f"pitch={self.gm.grid_pitch} um"
        ]
        for r in self.results:
            status = "OK" if r.success else "FAIL"
            n_wp = len(r.waypoints)
            lines.append(f"  [{status}] {r.name}: {n_wp} waypoints")
            if r.grid_result:
                lines.append(f"    BFS: {r.grid_result.stats}")
        return "\n".join(lines)

    def debug_grid_ascii(self, max_rows=40, max_cols=80) -> str:
        """Return an ASCII representation of the grid for debugging."""
        rows = min(self.gm.rows, max_rows)
        cols = min(self.gm.cols, max_cols)
        lines = []
        for r in range(rows):
            row_str = ""
            for c in range(cols):
                cell = self.router.grid[r][c]
                if (r, c) in self.router._net_map:
                    row_str += "█"
                elif cell == -1:  # OBSTACLE
                    row_str += "▓"
                else:
                    row_str += "·"
            lines.append(row_str)
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# PF BUNDLE ROUTER — Dijkstra with cost-field attraction
# ════════════════════════════════════════════════════════════════

class PFBundleRouter:
    """
    Grid-based bundle router for PhotonForge terminal routing.

    Routes bus signals as compact parallel groups. First net uses BFS
    (shortest path), subsequent nets use Dijkstra with a cost field
    that attracts them toward existing routes.

    Cost field parameters (all in grid cells):
      spacing:      min distance from existing routes (blocked)
      sweet_spot:   ideal parallel distance (lowest cost → attraction)
      attract_cost: how cheap the sweet spot is (lower = stronger pull)
      falloff:      cost increase per cell beyond sweet spot
      stray_cost:   max cost cap far from routes
    """

    def __init__(
        self,
        bbox_min: tuple[float, float],
        bbox_max: tuple[float, float],
        grid_pitch: float,
        margin: int = 5,
        cost_field: CostField | None = None,
    ):
        self.gm = compute_grid_mapping(bbox_min, bbox_max, grid_pitch, margin)
        self.router = BundleRouter(self.gm.rows, self.gm.cols, cost_field)
        self.terminal_pairs: list[TerminalPair] = []
        self.results: list[PFRouteResult] = []
        self._obstacle_cells: set[tuple[int, int]] = set()

    @property
    def grid_pitch(self) -> float:
        return self.gm.grid_pitch

    @property
    def cost_field(self) -> CostField:
        return self.router.cost_field

    def add_obstacles_from_layer(
        self,
        component: pf.Component,
        layer,
        margin: int = 0,
    ):
        """Rasterize all structures on a layer as obstacles."""
        cells = rasterize_structures(self.gm, component, layer, margin)
        self.router.add_obstacles(cells)
        self._obstacle_cells.update(cells)

    def add_obstacle_rect(
        self,
        x_min: float, y_min: float,
        x_max: float, y_max: float,
        margin: int = 0,
    ):
        """Add a rectangular obstacle region in layout coordinates."""
        cells = rasterize_bbox(self.gm, x_min, y_min, x_max, y_max, margin)
        self.router.add_obstacles(cells)
        self._obstacle_cells.update(cells)

    def add_terminal_pair(
        self,
        name: str,
        terminal1: pf.Terminal,
        terminal2: pf.Terminal,
    ):
        """Register a pair of terminals to route as a bus group."""
        self.terminal_pairs.append(TerminalPair(name, terminal1, terminal2))

    def _get_terminal_footprint(
        self,
        terminal: pf.Terminal,
        margin: int = 0,
    ) -> list[tuple[int, int]]:
        bb_min, bb_max = terminal.bounds()
        return rasterize_bbox(
            self.gm, bb_min[0], bb_min[1], bb_max[0], bb_max[1],
            margin=margin,
        )

    def route_all(
        self,
        trace_width: float,
        layer=None,
    ) -> list[PFRouteResult]:
        """
        Route all terminal pairs as a bus bundle.

        First net: BFS shortest path.
        Subsequent nets: Dijkstra with cost-field attraction toward
        existing routes, producing compact parallel bundles.

        Uses the same pad reservation logic as PFMazeRouter.
        """
        net_infos = []
        for tp in self.terminal_pairs:
            c1 = tp.terminal1.center()
            c2 = tp.terminal2.center()
            src = self.gm.layout_to_grid(c1[0], c1[1])
            tgt = self.gm.layout_to_grid(c2[0], c2[1])
            pad1 = set(self._get_terminal_footprint(tp.terminal1, margin=0))
            pad2 = set(self._get_terminal_footprint(tp.terminal2, margin=0))
            exit1 = set(self._get_terminal_footprint(tp.terminal1, margin=1))
            exit2 = set(self._get_terminal_footprint(tp.terminal2, margin=1))
            net_infos.append({
                "name": tp.name, "source": src, "target": tgt,
                "pad1": pad1, "pad2": pad2,
                "exit1": exit1, "exit2": exit2,
            })

        # Route nets one at a time: first BFS, rest Dijkstra
        self.results = []
        for i, (tp, info) in enumerate(zip(self.terminal_pairs, net_infos)):
            route_layer = layer if layer is not None else tp.terminal1.routing_layer

            # Pad reservation: clear current net's exit zone, re-block others
            my_exit = info["exit1"] | info["exit2"]
            for r, c in my_exit:
                self.router.clear_cell(r, c)

            # Re-block other pads' FULL exit zones (interior + border)
            other_exits = set()
            for j, other_info in enumerate(net_infos):
                if j != i:
                    other_exits.update(other_info["exit1"])
                    other_exits.update(other_info["exit2"])
            reblock = other_exits & my_exit
            self.router.add_obstacles(list(reblock))

            # Route: BFS for first net, Dijkstra with attraction for rest
            if i == 0:
                path, stats = self.router._run_bfs(info["source"], info["target"])
                result = RouteResult(
                    net_name=info["name"], source=info["source"],
                    target=info["target"], success=len(path) > 0,
                    path=path, stats=stats,
                )
                if result.success:
                    self.router._commit_path(path, info["name"])
                self.router.routed_nets.append(result)
            else:
                result = self.router.route_dijkstra(
                    info["source"], info["target"], info["name"],
                )

            # Restore: re-block cleared cells not on path
            path_set = set(result.path) if result.success else set()
            for cell in my_exit:
                if cell not in path_set:
                    self.router.add_obstacle(*cell)

            if not result.success:
                self.results.append(PFRouteResult(
                    name=tp.name, success=False, grid_result=result,
                ))
                continue

            waypoints = grid_path_to_layout_waypoints(self.gm, result.path)
            comp = self._create_route_component(
                tp.name, waypoints, trace_width, route_layer,
            )
            self.results.append(PFRouteResult(
                name=tp.name, success=True, grid_result=result,
                waypoints=waypoints, component=comp,
            ))

        return self.results

    def _create_route_component(
        self,
        name: str,
        waypoints: list[tuple[float, float]],
        trace_width: float,
        layer,
    ) -> pf.Component:
        comp = pf.Component(f"bundle_route_{name}")
        if len(waypoints) < 2:
            return comp
        path = pf.Path(waypoints[0], trace_width).segment(waypoints[1:])
        comp.add(layer, path)
        return comp

    def summary(self) -> str:
        cf = self.cost_field
        lines = [
            f"PFBundleRouter: grid {self.gm.rows}x{self.gm.cols}, "
            f"pitch={self.gm.grid_pitch} um",
            f"  CostField: spacing={cf.spacing}, sweet_spot={cf.sweet_spot}, "
            f"attract={cf.attract_cost}, falloff={cf.falloff}",
        ]
        for r in self.results:
            status = "OK" if r.success else "FAIL"
            algo = "BFS" if r.grid_result and "expansion_steps" in r.grid_result.stats else "Dijkstra"
            cost = r.grid_result.stats.get("total_cost", "-") if r.grid_result else "-"
            lines.append(f"  [{status}] {r.name}: {len(r.waypoints)} wp, {algo}, cost={cost}")
        return "\n".join(lines)

    def debug_grid_ascii(self, max_rows=40, max_cols=80) -> str:
        rows = min(self.gm.rows, max_rows)
        cols = min(self.gm.cols, max_cols)
        lines = []
        for r in range(rows):
            row_str = ""
            for c in range(cols):
                cell = self.router.grid[r][c]
                if (r, c) in self.router._net_map:
                    row_str += "█"
                elif cell == -1:
                    row_str += "▓"
                else:
                    row_str += "·"
            lines.append(row_str)
        return "\n".join(lines)
