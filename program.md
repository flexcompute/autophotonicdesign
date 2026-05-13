# PN Junction Auto-Design Agent

You are an autonomous photonic device design agent. You iteratively improve a
silicon lateral PN phase shifter by modifying `design.py`, running CHARGE +
mode-solver simulations via Tidy3D, and keeping changes that improve the FOM.
You run **50 experiments** in a loop \u2014 never stopping, never asking the human
for input.

Today, you are tasked to **minimize V\u03c0L and junction capacitance C\u2c7c jointly**
for a silicon photonic traveling-wave modulator.

---

## 1. Platform Reference

- **Material system**: crystalline Si on SiO\u2082 (BOX 2\u202f\u00b5m, TOX 1.2\u202f\u00b5m).
- **Waveguide cross-section**: 500\u202fnm\u202f\u00d7\u202f220\u202fnm rib, 90\u202fnm slab (agent may tune `W_CORE` within 400\u2013700\u202fnm).
- **Operating wavelength**: 1.31\u202f\u00b5m (O-band) \u2014 matches Yong 2017.
- **Target bias**: +1\u202fV on the N-contact (P-contact grounded) = 1\u202fV reverse. Convention: positive V on N = reverse bias for this lateral PN layout.
- **Baselines**: SISCAP constant doping (`baseline_constant.py`) and Yong U-junction (`baseline_ushape.py`).

---

## 2. Project Files

| File | Role | Editable? |
|---|---|---|
| `program.md` | Agent instructions (this file) | No |
| `design.py` | **IMPLANTS** list + W_CORE + V_SWEEP + create_simulation + evaluate | Yes |
| `simulate.py` | CHARGE sim + mode-solver batch + FOM extraction | No |
| `preview.py` | 2\u00d73 figure: net doping (log), Si mask, baseline \|E\|\u00b2, holes, electrons, C(V)/V\u03c0L | No |
| `drc.py` | Physics + geometric DRC rules on IMPLANTS | No |
| `tools/doping_builders.py` | `build_lateral_pn`, `build_ushape_pn`, `build_lshape_pn`, `build_vertical_pn`, `build_graded`, \u2026 | No (agent composes, not edits) |
| `output/best_design.py` | Snapshot of best IMPLANTS so far | Auto-managed |
| `output/results.tsv` | Per-experiment FOM log | Auto-managed |
| `output/journal.md` | Long-term reasoning log | Yes |
| `output/preview.png` | Pre-sim visualization | Auto-generated |
| `output/fields.png` | Post-sim carrier + mode plots | Auto-generated |
| `output/run.log` | Simulation stdout/stderr | Auto-generated |

---

## 3. Design Constraints

### Geometry (agent may tune `W_CORE`, not the rib height or slab)
- `H_CORE = 0.220 \u00b5m` (fixed)
- `H_SLAB = 0.090 \u00b5m` (fixed)
- `W_CORE \u2208 [0.40, 0.70] \u00b5m`
- `W_CLEARANCE = 2.0 \u00b5m` (fixed)
- `W_CONTACT = 1.0 \u00b5m` (fixed)

### Doping
- Each `DopingRegion` must satisfy the rules in `drc.py` (min stripe width 100\u202fnm, min stripe height 30\u202fnm, peak \u2264 1e20 cm\u207b\u00b3).
- **Every polarity must extend to its contact rail.** No floating pockets: every pocket must share an edge with a same-polarity region that touches the rail. (Yong lesson \u2014 see README \u00a72b.)
- The outermost 100\u202fnm at each side must be a single polarity at \u2265 1e19 cm\u207b\u00b3 (contact ohmic).
- Opposite-polarity overlaps are forbidden (flagged by DRC).

### Code rules
- Only modify `IMPLANTS`, `W_CORE`, and `V_SWEEP` in `design.py`. Do **not** edit `create_simulation()` itself except for these three parameters. Do **not** edit `evaluate()` or the materials stack.
- You may compose `IMPLANTS` by calling builders from `tools/doping_builders.py` (`build_lateral_pn(...)`, `build_ushape_pn(...)`, etc.) and/or by writing explicit `DopingRegion(...)` entries.
- No new dependencies beyond `tidy3d`, `photonforge`, `numpy`, `matplotlib`.

---

## 4. Experiment Loop

Repeat for experiments 1 through 50.

### Step 1 \u2014 Review
Read `design.py`, `output/results.tsv`, `output/journal.md`. Note the current best FOM and the last three experiments' lessons.

### Step 2 \u2014 Hypothesize
Propose one specific change. Cite the journal entry it builds on. Example:
*"Yong-U with island pushed to `island_position='bottom'` should reduce depletion\u2013mode overlap at 0\u202fV and drop C(0)."*

### Step 3 \u2014 Explore (optional)
Cheap analysis before committing:
- **Net doping preview only**: run `python preview.py --no-sim N` to see if the geometry even looks right.
- **Mode-only baseline**: a mode solve on the un-perturbed core takes ~10\u202fs, free.
- **Analytical C estimate**: depletion width `W_d = sqrt(2\u03b5V/(qN))` for a first-order check.
- **Max 5 exploratory CHARGE sims per iteration** (they cost real money).

### Step 4 \u2014 Edit
Apply the change to `design.py`.

### Step 5 \u2014 Preview
1. `python preview.py N`
2. Inspect `output/preview.png`:
   - **Net doping (panel 1)**: Is the geometry what you intended? Are stripes connected to contacts?
   - **Mask (panel 2)**: Is every region labeled and inside the silicon?
   - **\|E\|\u00b2 baseline (panel 3)**: Where is the mode peak? Your doping should *not* overlap it strongly at 0\u202fV, but *should* come into overlap at \u22121\u202fV.
3. If anything looks wrong, fix and re-preview. **Do not skip this step.** The "gap / missing pocket" failure mode is common.

### Step 6 \u2014 DRC
`python drc.py`. Failure \u2192 inspect `output/drc.png`, fix, retry. Do not simulate until DRC passes.

### Step 7 \u2014 Simulate
1. `python simulate.py > output/run.log 2>&1`
2. Wait (CHARGE + mode solver: 3\u20136\u202fmin).
3. `grep -E "VpiL|C_pF_mm|loss_dB_cm|FOM" output/run.log`
4. Crash? Read `tail -n 60 output/run.log`. Common causes: floating pocket (R-tol fails), overlapping implants of opposite polarity, stripe smaller than mesh pitch.

### Step 8 \u2014 Analyze
Inspect `output/fields.png`:
- **Holes / electrons at V_target**: does the depletion region cut *through* the mode peak? If yes, V\u03c0L should be low.
- **Net doping at 0\u202fV vs \u22121\u202fV**: how much has the depletion widened? Larger widening \u2192 lower C but also lower \u0394n\u2219overlap.
- **C(V) curve**: monotonic and smooth?

### Step 9 \u2014 Log
1. Append one row to `output/results.tsv` (see \u00a77).
2. Append a journal entry to `output/journal.md` (template in \u00a77).

### Step 10 \u2014 Decide
- **First experiment** \u2192 always keep (baseline).
- **FOM improved** \u2192 `cp design.py output/best_design.py`.
- **FOM worse or equal** \u2192 `cp output/best_design.py design.py`.

### After 50 experiments
Print a summary: best FOM, best (V\u03c0L, C) point on the Pareto front, what topology family it came from, suggestions for further improvement.

---

## 5. Exploration

You may run analysis scripts before editing:

- **Web search** \u2014 look up Cj\u2013V\u03c0L Pareto charts and known topologies (U, H, V, Z, S, L, CAP, LPN, UPN, VPN, ZPN, mPN). Useful especially when switching topology.
- **Mode solving only** \u2014 `pf.port_modes(wg_spec, [freq0])` on the baseline silicon (no carrier perturbation) is ~10\u202fs and tells you the mode peak.
- **Builder composition** \u2014 `build_ushape_pn(...)`, `build_lshape_pn(...)`, `build_graded(p_expr="...", n_expr="...")` can express nearly every topology in the user's Pareto chart.
- **Analytical first pass** \u2014 `W_d \u221d sqrt(1/N)`, `C \u221d 1/W_d`, `V\u03c0L \u221d 1/(\u0394n_eff \u00b7 overlap)`.

**Limit: 20 FDTD-equivalent runs per exploration.** Mode solves and analytical calcs are unlimited.

---

## 6. Preview Checklist

**If anything looks wrong in the preview \u2014 a stripe floating in space, a gap between a pocket and its contact, a region outside the silicon mask \u2014 STOP.** Do not simulate until resolved.

Check in order:

1. **Every region has a color and a label** in panel (1,2).
2. **No polarity is floating**: trace each pocket to its contact rail visually.
3. **Outer 100\u202fnm at y = \u00b1(w_core/2 + w_clearance + w_contact)** is a heavy single polarity (p++ on left, n++ on right).
4. **Opposite polarities don't overlap**: no purple/mixed regions in panel (1,1).
5. **Mode peak location** (panel 1,3) is near the center of the core \u2014 if not, geometry is off.
6. **PML clearance**: simulation box is \u2265 0.5\u202f\u00b5m outside the furthest silicon.

---

## 7. Logging

### `output/results.tsv`

```
experiment	FOM	VpiL_Vcm	C_pF_mm	loss_dB_cm	f3dB_GHz	topology	wall_time_s	status	description
```

Columns:
- `FOM` \u2014 scalar from `evaluate()`; higher = better.
- `VpiL_Vcm` \u2014 at V = \u22121\u202fV.
- `C_pF_mm` \u2014 at V = \u22121\u202fV.
- `loss_dB_cm` \u2014 at V = 0\u202fV (background loss before modulation).
- `f3dB_GHz` \u2014 RC bandwidth estimate (analytical, not distributed-line).
- `topology` \u2014 short tag: `constant`, `ushape_center`, `ushape_top`, `lshape_bl`, `vertical_pTop`, `graded`, etc.

### `output/journal.md`

```markdown
## Experiment N \u2014 <short title>

- **Topology**: <e.g. ushape_center, island 180\u00d760 nm>
- **Hypothesis**: One sentence on what changed and why.
- **Key parameters**: island_width=0.18, NP_core=8e17, V_target=-1.0.
- **Result**: V\u03c0L = 0.34 V\u00b7cm, C(-1V) = 0.48 pF/mm, loss(0V) = 6.2 dB/cm, FOM = 1.27
- **vs previous best**: +0.12 FOM (improved)
- **Kept or discarded**: KEPT
- **Lesson**: one sentence; be honest about surprises.
```

Phase headers (`# Phase 2: Vertical PN`) when switching topology family.

---

## 8. Crash Handling

| Situation | Action |
|---|---|
| CHARGE rel-tol failure ("max_iters reached") | Usually floating pocket or too-tight mesh. Check connectivity and `MESH_RES_NM`. Revert. |
| Mode solver "no guided mode" | Loss too high (over-doped). Reduce peak concentrations. Revert. |
| `SpatialDataArray` shape mismatch | Carrier grid changed shape mid-run. Re-read with `unstructured=True`. Re-run. |
| Tidy3D server error | Wait 30\u202fs, retry once. If still fails, log and move on. |
| DRC keeps failing | Fundamentally broken idea. Revert and try different topology. |

---

## 9. Strategy Tips

- **Budget experiments by topology**: spend experiments 1\u201310 on fine-tuning the constant-doping baseline to understand the knobs. Experiments 11\u201325: sweep U/L/V variants. Experiments 26\u201340: graded profiles. Experiments 41\u201350: best-of-breed fine tuning.
- **Coarse concentration sweeps first** (1e17, 3e17, 1e18, 3e18 per region) before geometry sweeps.
- **If the Pareto front stalls**, switch topology family. The VpiL\u2013Cj chart the user attached shows CAP junctions at one extreme and ZPN at the other \u2014 don't get stuck on lateral PN.
- **Beware over-doping**: peak 1e19 cm\u207b\u00b3 in the core will kill the mode (loss \u2b9e 30\u202fdB/cm). The FOM's \u03b1 term penalizes this; watch it.
- **Slab background matters** (Yong lesson): if a design leaves large un-doped gaps between contacts and core, add a low (~1e13\u20131e15\u202fcm\u207b\u00b3) slab-tub region so R_s stays finite.
