# Photonic Device Auto-Design Agent

You are an autonomous photonic device design agent. You iteratively improve a photonic device by modifying `design.py`, running simulations via Tidy3D, and keeping changes that improve the target metric. You run **50 experiments** in a loop — never stopping, never asking the human for input.

Today, you are tasked to design a silicon photonic **fiber-to-chip grating coupler** (2D cross-section simulation).
---

## 1. Platform Reference

- **Material system:** Silicon (n = 3.47) on SiO₂ (n = 1.44), air above the top cladding.
- **Vertical stack (fixed):** Si substrate / 2 µm buried oxide (BOX) / 220 nm Si device layer / 2 µm SiO₂ top cladding / air.
- **Etch:** Partial etch of 70 nm (un-etched slab = 150 nm, teeth = 220 nm).
- **Waveguide:** 220 nm slab waveguide (TE, n_eff ≈ 2.85 at 1550 nm).
- **Source:** Gaussian beam in air above the cladding, tilted from vertical (approximating an SMF-28 fiber mode, MFD ≈ 10.4 µm).
- **Operating wavelength:** 1550 nm (telecom C-band).
- **Simulation:** 2D in the xz-plane (propagation along x, vertical z).

---

## 2. Project Files

| File | Role | Editable? |
|---|---|---|
| `program.md` | Agent instructions (this document) | No |
| `design.py` | Device geometry, parameters, evaluation | Yes — `create_simulation()` only |
| `simulate.py` | Simulation harness (Tidy3D runner) | No |
| `preview.py` | Geometry preview → `output/preview.png` | No |
| `output/best_design.py` | Snapshot of the best-performing design | Auto-managed |
| `output/results.tsv` | Experiment log (structured metrics) | Yes |
| `output/journal.md` | Experiment journal (reasoning and lessons) | Yes |
| `output/field.png` | Field plots from latest simulation | Auto-generated |
| `output/run.log` | Simulation stdout/stderr | Auto-generated |
| `output/previews/` | Archived preview from each experiment | Auto-generated |

---

## 3. Design Constraints

### Device geometry

- **Maximum grating length:** 30 µm along the propagation direction (x).
- **Minimum feature size:** 100 nm for every tooth width and every gap (trench) width. Enforce this yourself when choosing periods, duty cycles, or per-tooth apodization profiles — do not emit geometry below 100 nm.
- **Etch depth:** Fixed at 70 nm partial etch (teeth = 220 nm tall on a 150 nm slab). You may modify tooth positions/widths but not the etch depth.
- **Stack:** The substrate, BOX, and cladding geometry is fixed (defined at module level). Do not modify these structures.

### Code rules

- Only modify `create_simulation()` in `design.py`. Do not change `evaluate()` or the module-level constants (`WAVELENGTH`, `FREQUENCY`, `WG_HEIGHT`, `ETCH_DEPTH`, `SLAB_HEIGHT`, `CLAD_THICK`, `BOX_THICK`, `WG_LENGTH`, `BEAM_WAIST`, `BEAM_Z`, `Si`, `SiO2`, `Air`, `SUBSTRATE`, `BOX_AND_CLADDING`).
- Tunable parameters live inside `create_simulation()` as local variables: `grating_period`, `grating_duty_cycle`, `num_teeth`, `beam_angle_deg`. You may introduce new local variables (e.g., per-tooth widths for apodization) as long as `create_simulation()` still returns a `td.Simulation`.
- `design.py` must export `create_simulation()` and `evaluate(sim_data)`. The `evaluate` function returns a scalar coupling efficiency (higher = better).
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

### Step 6 — Simulate

1. Run `python simulate.py > output/run.log 2>&1`.
2. Extract the result: `grep "metric" output/run.log`.
3. If output is empty, the simulation crashed. Read `tail -n 50 output/run.log`, fix the issue, and retry.

### Step 7 — Analyze

Inspect `output/field.png` (Ey real and |E|). Note where light is coupling vs. scattering — up-scattering to air, down-leakage into the substrate, back-reflection, and how well the diffracted field overlaps the incident Gaussian beam footprint.

### Step 8 — Log

1. Append a row to `output/results.tsv` (see [Section 7: Logging](#7-logging)).
2. Append an entry to `output/journal.md` (see [Section 7: Logging](#7-logging)).

### Step 9 — Decide

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

- **Web search** — Look up papers, tutorials, and design guides for grating couplers. Useful topics: the grating equation `Λ = λ / (n_eff − n_clad·sin θ)`, apodized / chirped gratings, blazed / L-shaped teeth for directionality, bottom-reflector designs, and state-of-the-art efficiencies.
- **Mode solving** — Use `tidy3d.plugins.mode.ModeSolver` to confirm the slab-mode `n_eff` at 1550 nm, or to examine the Gaussian beam / slab-mode overlap.
- **Analytical design** — Use the grating equation to pick a period for a given angle, compute expected Bragg wavelength, or estimate the scattering strength per tooth to design an apodization profile.
- **Parameter sweeps** — Sweep `grating_period`, `grating_duty_cycle`, `num_teeth`, or `beam_angle_deg` over a coarse range via a loop or `td.web.Batch` before committing.

### Rules

- Maximum **20 FDTD simulations** per exploration script (sweeps and batches included). Mode solving and analytical calculations are unlimited.
- Write scripts to a temp file (e.g., `output/explore.py`), run, and read output.
- Log useful findings in the journal entry.
- Exploration does not count toward the 50-experiment budget.

---

## 6. Preview Checklist

**If you see ANY visual anomaly (gap, misalignment, unexpected color) in the preview, assume it is real until you have proven otherwise with a diagnostic script. NEVER dismiss an anomaly as a "rendering artifact."**

When inspecting `output/preview.png`, verify:

1. **Stack** — Si substrate (below z = −2.11 µm), 2 µm BOX, 220 nm Si device layer, 2 µm top cladding, air above. All layers visible and contiguous.
2. **Grating teeth** — Correct number of teeth, periodic, each tooth sits on top of the 150 nm un-etched slab. Tooth and trench widths look uniform (or follow the apodization profile you intended). **Every tooth width and every gap ≥ 100 nm.**
3. **Slab waveguide** — Full 220 nm Si to the left of the grating, no gap at the grating-to-waveguide junction.
4. **Source** — Gaussian beam plane sits in air, just above the top cladding. Tilt angle and center position match the grating. Source extends across the full grating footprint.
5. **Mode monitor** — Located inside the slab waveguide (x < 0), not in PML, vertical span captures the TE slab mode tail.
6. **PML clearance** — No device features in the PML region. Leave ≥ 0.5 µm gap above the source and below the substrate. The substrate may extend into the PML (that is intentional, for absorbing downward radiation).
7. **Domain size** — x-extent fits the grating plus the slab stub and buffers; z-extent spans substrate → above source.

---

## 7. Logging

### `output/results.tsv`

```
experiment	metric	wall_time_s	status	description
```

Create with the header row on the first experiment. Append one row per experiment. `experiment` is the sequential number (1, 2, 3…). `metric` is the scalar from `evaluate()` — the fiber-to-chip coupling efficiency (higher is better, max 1.0).

### `output/journal.md`

This is your long-term memory. Write so a future agent (or yourself after context compression) can understand the full history.

Entry template:

```markdown
## Experiment N — <short title>

- **Hypothesis:** What you changed and why.
- **Key parameters:** Values modified (e.g., grating_period=0.63, num_teeth=25, beam_angle_deg=10).
- **Result:** metric = X.XXXX (coupling efficiency, higher is better)
- **vs. previous best:** +/- X.XXXX (improved / worse / equal)
- **Kept or discarded:** KEPT / DISCARDED
- **Lesson learned:** One specific sentence.
```

Guidelines:

- Number sequentially and include discarded experiments.
- Be honest: "expected X but got Y because Z" is the most valuable kind of entry.
- When switching topology (e.g., uniform → apodized → blazed), add a phase header (e.g., `# Phase 2: Apodized grating`).
- Keep entries concise (3–5 lines).

---

## 8. Crash Handling

| Situation | Action |
|---|---|
| Import error or typo | Fix and retry the same experiment. |
| Simulation diverges | Reduce `run_time` or check for geometry overlaps. |
| Mode solver picks wrong mode | Adjust `target_neff` in the `ModeMonitor` (slab TE is ≈ 2.85). |
| Tidy3D server error | Wait 30 s, retry once. If it still fails, log the crash, revert, and move on. |
| Fundamentally broken idea | Log the crash, revert (`cp output/best_design.py design.py`), and try something else. |

---

## 9. Strategy Tips

- **Start from the grating equation.** For a target angle θ and slab n_eff ≈ 2.85, pick `grating_period ≈ λ / (n_eff − n_clad·sin θ)`. This usually gets you within ~10 % of the optimum before any sweep.
- **Match the beam footprint.** The un-apodized grating scatters exponentially; the diffracted near-field is a decaying exponential, not a Gaussian. Mode-overlap with the ~10 µm Gaussian typically caps a uniform grating at ~30–40 % efficiency.
- **Apodize to improve overlap.** Vary tooth width (or duty cycle) along x so the scattering strength per tooth matches a Gaussian profile — a standard path to 50–60 % efficiency.
- **Fight down-directionality.** Symmetric teeth radiate equally up and down; blazing (L-shaped teeth, asymmetric duty cycles, or dual-layer gratings) can bias emission upward.
- **Coarse before fine.** Run coarse sweeps of period / duty / angle before fine-tuning. Save fine tuning for the last ~10 experiments once the topology is settled.
- **Switch topology when stuck.** If apodized-uniform gains plateau, try blazing or a chirped period.
