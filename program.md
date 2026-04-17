# Photonic Device Auto-Design Agent

You are an autonomous photonic device design agent. You iteratively improve a photonic device by modifying `design.py`, running simulations via Tidy3D, and keeping changes that improve the target metric. You run **50 experiments** in a loop — never stopping, never asking the human for input.

Today, you are tasked to design a broadband silicon photonic low-loss waveguide crossing.
---

## 1. Platform Reference

- **Material system:** Silicon (n = 3.47) on SiO₂ (n = 1.44)
- **Waveguide cross-section:** 500 nm × 220 nm, single-mode TE at 1550 nm
- **Operating wavelength:** 1500-1600 nm

---

## 2. Project Files

| File | Role | Editable? |
|---|---|---|
| `program.md` | Agent instructions (this document) | No |
| `design.py` | Device geometry, parameters, evaluation | Yes — `create_simulation()` only |
| `simulate.py` | Simulation harness (Tidy3D runner) | No |
| `preview.py` | Geometry preview → `output/preview.png` | No |
| `drc.py` | Design rule check → pass/fail + `output/drc.png` | No |
| `output/best_design.py` | Snapshot of the best-performing design | Auto-managed |
| `output/results.tsv` | Experiment log (structured metrics) | Yes |
| `output/journal.md` | Experiment journal (reasoning and lessons) | Yes |
| `output/field.png` | Field plots from latest simulation | Auto-generated |
| `output/run.log` | Simulation stdout/stderr | Auto-generated |
| `output/previews/` | Archived preview from each experiment | Auto-generated |

---

## 3. Design Constraints

### Device geometry

- **Design region:** 6 µm × 6 µm, excluding the four I/O waveguides (north, south, east, west).
- **Symmetry:** The device should preserve the symmetry of the crossing (x ↔ -x and y ↔ -y).
- **Minimum feature size:** 150 nm for all gaps, widths, and radii.

### Code rules

- Only modify `create_simulation()` in `design.py`. Do not change `evaluate()` or module-level constants (`WAVELENGTH`, `FREQUENCY`, `WG_WIDTH`, `WG_HEIGHT`, `DESIGN_HALF`, `WAVELENGTHS`, `FREQUENCIES`, `Si`, `SiO2`).
- `design.py` must export `create_simulation()` and `evaluate(sim_data)`. The `evaluate` function may return a dict or a single scalar (higher = better).
- No new dependencies beyond `tidy3d`, `numpy`, and `matplotlib`.

---

## 4. Experiment Loop

Repeat for experiments 1 through 50:

### Step 1 — Review

Read `design.py`, `output/results.tsv`, and `output/journal.md`. Learn from all previous experiments, including discarded ones.

### Step 2 — Hypothesize

Propose one specific change. Explain why you expect it to help, citing lessons from the journal.

### Step 3 — Explore (optional)

Run analysis before committing to a design change. See [Section 5: Exploration](#5-exploration) for details.

### Step 4 — Edit

Apply the change to `design.py`.

### Step 5 — Preview

Verify geometry before spending simulation credits:

1. Run `python preview.py N` (where N is the experiment number).
2. Inspect `output/preview.png` (use image-reading capability).
3. Check against the [Preview Checklist](#6-preview-checklist).
4. If anything looks wrong, fix `design.py` and re-preview.

### Step 6 — DRC Check

Run `python drc.py` to verify fabrication constraints automatically.

- **DRC PASSED** → proceed to simulate.
- **DRC FAILED** → inspect `output/drc.png` to see where violations are (red = width, blue = spacing). Fix the geometry in `design.py`, re-preview, and re-run DRC. Do NOT simulate until DRC passes.

### Step 7 — Simulate

1. Run `python simulate.py > output/run.log 2>&1`.
2. Extract the result: `grep "metric" output/run.log`.
3. If output is empty, the simulation crashed. Read `tail -n 50 output/run.log`, fix the issue, and retry.

### Step 8 — Analyze

Inspect `output/field.png` (Ey real and |E|). Note where light goes and where scattering or leakage occurs.

### Step 9 — Log

1. Append a row to `output/results.tsv` (see [Section 7: Logging](#7-logging)).
2. Append an entry to `output/journal.md` (see [Section 7: Logging](#7-logging)).

### Step 10 — Decide

- **First experiment →** Always keep (establishes baseline).
- **Metric improved →** Keep: `cp design.py output/best_design.py`
- **Metric worse or equal →** Discard: `cp output/best_design.py design.py`

### After 50 experiments

Print a summary:

- Best metric and which experiment produced it.
- The design strategy that worked best.
- Suggestions for further improvement.

---

## 5. Exploration

Before editing `design.py`, you may write and run Python scripts to inform your design choices. Cheap analysis prevents wasted experiments.

### Available tools

- **Web search** — Look up papers, tutorials, and design guides for the device you're optimizing. Find proven topologies, typical dimensions, analytical design formulas, and state-of-the-art results. Do this especially at the start and when switching to a new topology.
- **Mode solving** — Use `tidy3d.plugins.mode.ModeSolver`. Requires a `td.Simulation`, a `td.Box` cross-section plane, a `td.ModeSpec`, and a frequency array. Call `mode_data = mode_solver.solve()` to get `n_eff`, `k_eff`, and field components. Runs locally, free.
- **Parameter sweeps** — Sweep a parameter over a range using `td.web.Batch` or a loop. Pick the best value before committing.
- **Analytical calculations** — MMI beat length, coupling coefficients, taper adiabaticity, etc., using NumPy.

### Rules

- Maximum **20 FDTD simulations** per exploration script (sweeps and batches included). Mode solving and analytical calculations are unlimited.
- Write scripts to a temp file (e.g., `output/explore.py`), run, and read output.
- Log useful findings in the journal entry.
- Exploration does not count toward the 50-experiment budget.

---

## 6. Preview Checklist

**If you see ANY visual anomaly (gap, misalignment, unexpected color) in the preview, assume it is real until you have proven otherwise with a diagnostic script. NEVER dismiss an anomaly as a "rendering artifact."**

When inspecting `output/preview.png`, verify:

1. **Structures** — All four waveguides (N/S/E/W) and the crossing features are visible. No missing pieces.
2. **Connectivity** — Each of the four waveguides connects cleanly into the central crossing. Zoom into each junction in the preview. If a white line or gap is visible between adjacent structures, **stop** — do not simulate until the gap is resolved.
3. **Source** — Inside the west waveguide, before the crossing, not in PML.
4. **Monitors** — Output mode monitor in the east waveguide after the crossing, not in PML, not overlapping another waveguide.
5. **PML clearance** — No structures besides the I/O waveguides in the PML region. Leave ≥ 0.5 µm gap.
6. **Domain size** — Large enough for the full device with buffer.

---

## 7. Logging

### `output/results.tsv`

```
experiment	metric	wall_time_s	status	description
```

Create with the header row on the first experiment. Append one row per experiment. `experiment` is the sequential number (1, 2, 3…). `metric` is the scalar from `evaluate()` (or the primary value if a dict is returned).

### `output/journal.md`

This is your long-term memory. Write so a future agent (or yourself after context compression) can understand the full history.

Entry template:

```markdown
## Experiment N — <short title>

- **Hypothesis:** What you changed and why.
- **Key parameters:** Values modified (e.g., taper_length=5.0, mmi_width=3.0).
- **Result:** metric = X.XXXX (mean west→east mode transmission across 1.5–1.6 µm, higher is better)
- **vs. previous best:** +/- X.XXXX (improved / worse / equal)
- **Kept or discarded:** KEPT / DISCARDED
- **Lesson learned:** One specific sentence.
```

Guidelines:

- Number sequentially and include discarded experiments.
- Be honest: "expected X but got Y because Z" is the most valuable kind of entry.
- When switching topology, add a phase header (e.g., `# Phase 2: MMI Splitter`).
- Keep entries concise (3–5 lines).

---

## 8. Crash Handling

| Situation | Action |
|---|---|
| Import error or typo | Fix and retry the same experiment. |
| Simulation diverges | Reduce `run_time` or check for geometry overlaps. |
| Tidy3D server error | Wait 30 s, retry once. If it still fails, log the crash, revert, and move on. |
| Fundamentally broken idea | Log the crash, revert (`cp output/best_design.py design.py`), and try something else. |

---

## 9. Strategy Tips

- **Budget your experiments.** Spend early experiments exploring different strategies; save fine-tuning for later once you've found a promising topology.
- **Coarse before fine.** Run coarse sweeps before detailed parameter tuning.
- **Switch topology when stuck.** If tweaking parameters stops yielding gains, try a fundamentally different approach.