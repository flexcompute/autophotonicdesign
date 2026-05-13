# AutoPhotonicDesign · Routing Branch

An autonomous design agent for chip-level electrical routing. Same
Karpathy-style autoresearch loop as
[`main`](https://github.com/flexcompute/autophotonicdesign), but the
"simulator" is a PhotonForge layout pass: the agent tunes a routing
strategy and the DRC violation count is the fitness signal.

## What it does

A 32-net PhotonForge projector circuit (16 AMZIs, each with two
thermo-optic phase shifters) needs every heater terminal connected to
a bondpad at the die edge. The shipped baseline is naive Manhattan
(`pf.parametric.route_manhattan`, each net routed alone) which produces
**192 DRC violations**:

- 30 routes crossing M1_heater (would short the heater to M2)
- 162 route × route intersections
- 0 pad × pad overlaps

The agent edits `design.py` to swap the routing strategy and tune
parameters. After ~27 iterations it converges on **0 violations** by
moving from Manhattan → BFS grid → A* → Bundle → Hybrid, then turning
on M1 obstacle blocking, increasing the cell margin, and inflating the
obstacle polygons.

## Layout

```
.
├── program.md            # Agent brief: device, constraints, loop rules
├── design.py             # THE ONLY FILE THE AGENT MODIFIES — MODE + CONFIG
├── route.py              # Runs one experiment, archives + scores
├── drc.py                # Quick pass/fail without archive
├── preview.py            # Renders current layout as SVG (free)
├── schematic.svg         # Loop diagram
├── tools/                # Load-bearing harness modules
│   ├── runners.py            # cfg_defaults, run_manhattan, run_grid
│   ├── projector_circuit_setup.py    # The 32-net AMZI projector
│   ├── routing_algorithms.py         # BFS, A*, Bundle, Rip-Up, Hybrid
│   ├── pf_routing_arena.py           # PhotonForge ↔ grid-world bridge
│   ├── pf_maze_router.py             # Single-net bridge
│   ├── maze_router.py                # Lee's algorithm reference
│   └── criteria.py                   # DRC scoring dataclass
├── output/               # Auto-generated; .gitignored
└── README.md
```

## Difference from the main (passive) template

Two notable differences:

1. **No cloud simulation.** Routing is pure CPU / PhotonForge work. A
   full `route.py` run is **~3 seconds** of routing + a one-time
   ~30 s import for PhotonForge + SiEPIC PDK. No FlexCredit cost.
2. **`route.py` instead of `simulate.py`.** There's no FDTD here, so
   the entry point is named for what it actually does.

The agent contract is otherwise identical: edit `design.py`, re-run
`python route.py`, inspect `output/journal.md` and `output/results.tsv`.

## Quickstart

```bash
# 1. Install dependencies (Python 3.10+)
pip install photonforge siepic-forge numpy matplotlib

# 2. Verify the layout renders (no cloud, no simulation)
python preview.py        # writes output/preview.svg

# 3. Run a DRC pre-flight on the iter-1 baseline
python drc.py            # prints 192 violations, exits 1

# 4. Run one full experiment with archive
python route.py --description "naive Manhattan baseline"

# 5. Hand off to the agent
claude "Follow the instructions in program.md and start designing!"
```

## Iter-1 baseline

`design.py` ships with `MODE = "manhattan_indep"`, `BLOCK_M1 = False`.
Expected metrics:

| metric | value |
|---|---|
| routed | 32 / 32 |
| heater violations | 30 |
| route × route | 162 |
| pad × pad | 0 |
| score | 1920 |
| wall time | ~3 s |

That's the starting point. The agent moves from there.

## Citation

If you use this in published work, please cite Flexcompute's
[Agentic Photonic Design for Routing](https://hs.flexcompute.com/blog/agentic-photonic-design-routing)
blog post and Tom's
[Learning Auto-Routing by Building](https://engineering.flexcompute.com/articles/electrical-routing-agents/)
essay.
