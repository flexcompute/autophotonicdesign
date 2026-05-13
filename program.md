# Routing Auto-Design Agent

You are an autonomous photonic-chip routing agent. You iteratively
improve an electrical-routing strategy by modifying `design.py`, running
the routing experiment with `python route.py`, and keeping changes
that lower the violation score. You run **30 experiments** in a loop,
never stopping, never asking the human for input.

Your task: take a fixed 32-net PhotonForge **projector circuit** (16 AMZIs,
each with two thermo-optic phase shifters that need a DC route to a
bondpad at the die edge) and produce a routed layout with **zero DRC
violations.** The starting baseline (`pf.parametric.route_manhattan`,
each net routed independently) produces ~192 violations.

---

## 1. Platform Reference

- **Layout engine:** PhotonForge (`photonforge`)
- **Routing layer:** M2 — GDS `(12, 0)` — 15 µm default trace width
- **Obstacle layer:** M1_heater — GDS `(11, 0)` — routing across this
  layer turns the heater into a heatsink and is a hard DRC failure
- **Circuit:** 16 AMZIs (`siepic_forge.ebeam` PDK), assembled
  geometry-only in `tools/projector_circuit_setup.py`. Each AMZI has
  two heater terminals (`T0`, `T1`). 32 routes total.
- **Bondpads:** 22 on top (y = +700 µm), 20 on bottom (y = −700 µm),
  120 µm pitch, x-shifted by −1500 µm

---

## 2. Project Files

| File | Role | Editable? |
|---|---|---|
| `program.md` | Agent instructions (this file) | No |
| `design.py` | `MODE` + `CONFIG` dict (routing strategy) | **Yes** |
| `route.py` | Runs one experiment, archives + scores | No |
| `drc.py` | Quick pass/fail without archive | No |
| `preview.py` | Renders current layout, no scoring | No |
| `tools/runners.py` | Reusable `run_manhattan`, `run_grid` functions | No |
| `tools/routing_algorithms.py` | BFS / A* / Bundle / Rip-Up / Hybrid | No |
| `tools/pf_routing_arena.py` | Grid-world ↔ PhotonForge bridge | No |
| `tools/criteria.py` | DRC scoring helpers | No |
| `output/experiments/NNNN/` | Auto-managed | Don't touch |
| `output/results.tsv` | Per-experiment log | Auto-managed |
| `output/journal.md` | Long-term reasoning log | Yes (you write entries) |

---

## 3. Design knobs (in `design.py`)

```python
MODE     = "manhattan_indep" | "manhattan_seq" | "grid"
CONFIG   = cfg_defaults(
    ALGORITHM    = "BFS" | "A*" | "Bundle" | "Rip-Up" | "Hybrid",  # only used when MODE == "grid"
    GRID_PITCH   = 25.0,         # µm  (10–50 sensible)
    TRACE_WIDTH  = 15.0,         # µm
    INFLATE_UM   = 0.0,          # polygon inflation in µm before rasterization
    MARGIN       = 1,            # cell margin around route obstacles
    M1_MARGIN    = 1,            # cell margin around heaters
    BLOCK_M1     = True,         # treat (11, 0) as obstacle
    BP_SPACING   = 120.0,        # bondpad x-pitch (µm)
    BP_X_SHIFT   = -1500.0,
    BP_Y_OFFSET  = 700.0,
    SPLIT        = "by_terminal" | "by_y",
    ASSIGNMENT   = "nearest" | "ordered",
    T0_APPROACH  = ("W", "N", "S"),
    T1_APPROACH  = ("E", "N", "S"),
    PAD_LAYOUT   = "single_row",
)
```

Out-of-the-box `design.py` ships with **iter-1 baseline**:
`MODE = "manhattan_indep"`, `BLOCK_M1 = False`. That run produces
~192 violations and is what the public blog post starts from.

---

## 4. Design Constraints

### Hard DRC rules (must all pass)
- `routed == n_total` — every net routed
- `heater_violations == 0` — no route crosses M1_heater
- `route_route_violations == 0` — no two routes share a cell
- `pad_pad_violations == 0` — no bondpad overlaps another

### Soft (rank passing configs)
- Bundling score — fraction of route cells with parallel neighbors
- Total wirelength — sum of cell counts
- Max turns per net

---

## 5. Experiment Loop

Repeat for experiments 1 through 30:

### Step 1 — Review
Read `output/results.tsv` and `output/journal.md`. Note the current best
score and the last three experiments' lessons.

### Step 2 — Hypothesize
Propose one specific change. Cite the journal entry it builds on.

### Step 3 — Edit
Modify `MODE` and/or `CONFIG` in `design.py`.

### Step 4 — Pre-flight
```bash
python drc.py
```
If DRC passes, the design is clean enough to commit. If it fails, you can
still run the full experiment to log progress, or rethink the change first.

### Step 5 — Run the full experiment
```bash
python route.py --description "<one-line summary of the change>"
```
This builds the projector circuit, runs the routing, scores DRC, and
archives the result to `output/experiments/NNNN/`. It prints a
`=== Results ===` block you can grep for `metric_score`.

### Step 6 — Decide
- **Score improved or first pass** → keep `design.py` as is, append a
  win to `output/journal.md`.
- **Score worse** → revert `design.py` from `output/experiments/<last_kept>/design.py`,
  append a lesson to `journal.md`.
- **Crash** → append the lesson, revert.

### After 30 experiments
Print a summary: best score, design strategy that worked, suggestions.

---

## 6. Strategy Tips

- The published blog post converged in **27 iterations**. Three phases:
  baseline (Manhattan), grid maze router exploration (BFS → A* →
  Bundle → Hybrid), obstacle-handling refinement (block M1, raise
  margin, inflate polygons).
- The very first improvement is usually **BLOCK_M1 = True** plus
  switching to a grid maze router.
- After turning the M1 obstacles on, `INFLATE_UM` (polygon inflation
  before rasterization) is the key remaining knob.
- Don't waste experiments on tiny pitch tweaks — each algorithm class
  is one experiment.

---

## 7. Output format

The agent should append to `output/journal.md` after every experiment:

```markdown
## Experiment 7 — block_m1_inflate2um

- **Hypothesis**: enable BLOCK_M1 and inflate 2 µm to push routes off
  the heater edges (last attempt overflowed by 8 cells along y=2)
- **Diff**: BLOCK_M1 True→True (was already True), INFLATE_UM 0→2
- **Result**: score 162→58 (improved), routed 32/32, heater=0, rr=14, pp=0
- **Kept**: yes
- **Lesson**: route–route is still the dominant violator class. Try
  bundling next, then rip-up.
```
