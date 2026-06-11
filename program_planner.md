# DoE Planner — program (Phase 0)

You are the **planning step**. You run BEFORE the packing loop. Your job: look at the device
**library** available on this platform and decide the Design-of-Experiments — which devices to
test, which parameter of each to sweep, over what range and how many points, and how many
replicates — then write a concrete plan the packing loop consumes.

You do not place or route anything. You decide *what to measure*. The packing loop (`program.md`)
then maximizes how much of your DoE fits the fixed 8 × 3 mm die, routed and gate-clean.

## Step 1 — look at the library

The library (`tools/library.py`, `default_library()`) is a set of `DeviceSource`s. Each source is
**either a PCell** (`@pf.parametric_component`, sweepable by argument) **or a GDS file** (loaded
with `pf.load_layout`, ports auto-detected). Both expose the same interface, so the plan is
agnostic to where a device came from. Run:

```
python plan.py
```

It prints, for every source: kind (pcell/gds), active/passive, optical-port and terminal counts,
what it measures, its sweepable parameters, and the real packed footprint of one measurement site.

## Step 2 — reason about what to measure

`SWEEP_KB` in `plan.py` holds the domain-informed sweeps; refine them with measurement judgement:

- **Cutback (straight / spiral `length`)**: points must span > a decade so the insertion-loss-vs-
  length fit gives a trustworthy slope (propagation loss) and intercept (coupling loss). The
  spiral carries the mm-scale arm a low-loss waveguide needs without a mm-long straight.
- **Directional coupler (`coupling_gap`, `coupling_length`)**: bracket the 50:50 point on both
  sides so the split-ratio curve can be interpolated; sweep the two DC axes separately.
- **Crossing (`arm_length`)**: vary the taper geometry for the crossing insertion-loss trend.
- **Thermo-optic heater (`length`, `heater_width`)**: choose values whose P_π differences are
  resolvable. Active — each site costs two bond pads of electrical IO.
- **Replicate-only / GDS devices**: no internal parameter, so seed a few replicates for
  process-uniformity sampling (`REPLICATE_HINT`).

Each device may get more than one experiment (e.g. the dcoupler sweeps gap AND length). The base
DoE should be a *fraction* of the die — the loop replicates it to fill. `plan.py` reports the
replicate multiplier the loop will need.

## Step 3 — write the plan

`plan.py` writes:
- `blackboard/doe_plan.json` — the machine-readable plan the loop reads (`experiments`: source /
  param / values / fixed / replicate_hint / measures / rationale).
- `blackboard/doe_plan.md` — the human rationale (one line per experiment).

To change the experiment, edit `SWEEP_KB` (and `REPLICATE_HINT`) and re-run `python plan.py`. To
change the devices, edit `default_library()` in `tools/library.py` (add your PCells / GDS files),
then re-run the planner — it will pick them up automatically.

## Output

A `blackboard/doe_plan.json` + `doe_plan.md` with a justified DoE. Hand off: the packing loop
(`program.md`) takes over from the plan.
