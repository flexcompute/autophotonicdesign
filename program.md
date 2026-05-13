# Segmented-CPW Auto-Design Agent

You are an autonomous RF/photonics design agent. You iteratively improve a
T-rail-loaded coplanar waveguide (CPW) electrode for a thin-film lithium
tantalate (LTOI300) Mach–Zehnder modulator by editing `design.py`, running a
3-D Tidy3D `TerminalComponentModeler` simulation, extracting transmission-line
parameters from the S-matrix, and keeping changes that improve the FOM. You
run **50 experiments** in a loop — never stopping, never asking the human
for input.

Your task: **jointly minimize microwave loss `α₀` (dB/cm/√GHz), match the
characteristic impedance `Z₀` to 50 Ω, and pull the RF effective index
`n_eff` up to 2.20** (the optical group index of TFLT TE @1310 nm). The
baseline `design.py` shipped on this branch is the iteration-1 T-rail CPW
design — it is the starting point for the agent.

---

## 1. Platform Reference

- **Material stack** (top → bottom):
  - Air
  - Au CPW + T-rails (`TM` thick, gold conductivity 41 S/μm)
  - SiO₂ cladding (`TSIO21` above LTOI; baseline 200 nm)
  - TFLT (LTOI300) ridge: 600 nm thick, 300 nm slab, 30° sidewall
  - SiO₂ BOX (2 μm)
  - Quartz substrate (εᵣ = 4.5)
- **Operating band**: 1–65 GHz (FDTD simulated). Headline metrics reported
  at `F_REF = 40 GHz` (clean of band-edge port-mode artifacts).
- **Optical waveguide** (frozen): 1.0 μm rib width, 600 nm core / 300 nm
  slab, anisotropic LiTaO₃ (εxx = 27.9 e-, εyy = εzz = 44 o-).
- **Operating point** (LXT collaboration): 67 GHz; n_eff target = 2.20
  matches optical group index of TE @1310 nm.

Baseline (experiment 0001):

| Metric | Value | Target |
|---|---|---|
| FOM | −1.12 | maximize |
| α₀ (dB/cm/√GHz) | 0.573 | minimize |
| α(40 GHz) (dB/cm) | 2.82 | minimize |
| Re(Z₀)(40 GHz) (Ω) | 39.4 | 50 |
| n_eff(40 GHz) | 2.02 | 2.20 |

---

## 2. Project Files

| File | Role | Editable? |
|---|---|---|
| `program.md` | Agent instructions (this file) | No |
| `design.py` | T-rail + CPW geometry + materials + FOM. **Edit only the parameters in the AGENT-TUNABLE block at the top.** | **Yes** |
| `preview.py` | 4-panel pre-sim view → `output/preview.png` | No |
| `drc.py` | Geometric + process DRC → pass/fail | No |
| `simulate.py` | Submits 3-D TCM, extracts S-params, computes FOM, archives the run | No |
| `tools/journal.py`, `tools/dashboard.py` | Logging + dashboard | No |
| `output/best_design.py` | Snapshot of best-FOM design | Auto |
| `output/results.tsv` | Per-experiment metric log | Auto |
| `output/journal.md` | Long-term reasoning log | **Yes — fill in stubs** |
| `output/dashboard.html` | Static dashboard (open in browser) | Auto |
| `output/experiments/NNNN/` | Per-experiment archive (frozen design.py + plots + results.json) | Auto |

---

## 3. Design Constraints

### Process-fixed (DO NOT change in `design.py`)

- TFLT thicknesses: `TLN0 = 0.600`, `TLN1 = 0.300` μm.
- Optical rib: `W0 = 1.0` μm, `THETA_LN_DEG = 30`.
- TFLT permittivities: `EPS_LN_O = 44`, `EPS_LN_EO = 27.9`.
- Quartz substrate: `EPS_QZ = 4.5`.
- Frequency band: `F_MIN = 1e9`, `F_MAX = 65e9`, `F_REF = 40e9`,
  `F_FIT_MIN/MAX = 5–50 GHz`.
- FOM weights and target values (`λ_Z = 5`, `λ_n = 50`, `target_Z = 50 Ω`,
  `target_n = 2.20`).
- BOX thickness `TSIO20 = 2.0` μm.
- Gold conductivity `SIGMA_AU_S_per_um = 41.0`.

### Fab rules (enforced by `drc.py`; failure aborts simulate)

- **Minimum metal feature & spacing: 100 nm.** Applies to `T_S`, `T_T`,
  `T_H`, `T_R`, `T_C`, `G`, `WS`, `WG`, and the residual ground-rail
  width `WG − (T_S + T_H)`.
- **Minimum metal thickness:** `TM ≥ 0.100` μm.
- **Cladding above LTOI can only INCREASE** from baseline:
  `TSIO21 ≥ 0.200` μm.
- T_R must fit inside the period: `T_R ≤ P_T − 0.10`, where
  `P_T = T_R + T_C`.
- `N_PERIODS ≥ 5` so the segmented section is long enough for reliable
  phase-slope extraction.

### Editable knobs (in `design.py`'s AGENT-TUNABLE block)

| Knob | Baseline | Role |
|---|---|---|
| `T_S` | 2.0 μm | T-top width along propagation |
| `T_R` | 45.0 μm | T-top length transverse to propagation |
| `T_H` | 6.0 μm | T-neck length (how far the T extends into the gap) |
| `T_T` | 2.0 μm | T-neck width along propagation |
| `T_C` | 5.0 μm | gap between adjacent T's along propagation |
| `G` | 5.0 μm | residual CPW gap (where the rib waveguide lives) |
| `WS` | 100.0 μm | signal trace width |
| `WG` | 300.0 μm | ground trace width |
| `TM` | 1.0 μm | metal thickness |
| `TSIO21` | 0.2 μm | cladding above LTOI (only ↑ from baseline) |
| `N_PERIODS` | 20 | number of T-rail unit cells (cost knob — agent may shrink to 10 for exploration) |

The **agent may not edit any other constant or function** in `design.py`.

---

## 4. Experiment Loop

Repeat for experiments 2 through 50 (1 = frozen baseline).

### Step 1 — Review

Read `output/results.tsv`, `output/journal.md`, and the last 3 experiment
folders' `results.json`. Note:
- Current best FOM and which knobs produced it.
- Which knob moves have been tried and their sign of effect on each of
  (α₀, Z₀, n_eff).
- Which ones are *unexplored* — those are usually the highest-information
  next move.

### Step 2 — Hypothesize

Propose ONE specific knob change. State the predicted direction of effect
on each of (α₀, Z₀, n_eff). Cite the journal entry it builds on.

Examples:
- *"Raise `T_H` from 6 → 8 μm: more capacitive loading per cell → expect
  n_eff ↑ and Z₀ ↓; α₀ slight ↑ (more current crowding at the neck).
  Builds on exp 4 which showed `T_R` already saturated."*
- *"Drop `G` from 5 → 3 μm: smaller residual gap → much higher C/μm →
  n_eff ↑ but Z₀ ↓ steeply. Compensate by widening `WS` next iteration."*
- *"Raise `TM` from 1 → 2 μm: thicker metal → α₀ ↓ (more conductor
  cross-section), n_eff and Z₀ unchanged to first order."*

### Step 3 — Explore (optional, free)

Cheap analysis before paying for a 3-D run:
- **Web search** — papers on T-rail / capacitively-loaded slow-wave CPW,
  especially for TFLN/TFLT operating bands. Look up `Z₀(L,C)`, slow-wave
  factor, conductor-loss formulas for CPW.
- **Analytical estimates** —
  - CPW `Z₀ ≈ (η₀ / √εᵣ_eff) · K(k')/K(k) / 4`, with `k = a/b` and
    `a, b` the inner/outer half-widths.
  - Slow-wave factor `(n_eff_loaded / n_eff_unloaded)² = C_loaded / C_unloaded`.
  - Skin-effect resistance `R_s = √(πfμ₀/σ)`.
- **2-D mode solver on the conventional CPW** — `python simulate.py
  --mode2d` is ~$0.02 / 30 s and tells you how the **host** CPW responds
  to changes in `G/WS/WG/TM/TSIO21`.

### Step 4 — Edit

Apply the change to `design.py`'s AGENT-TUNABLE block.

### Step 5 — Preview

```
python preview.py
```

Inspect `output/preview.png`:
- All four T's per row visible? Rib waveguide visible in the active gap?
- Top view: are the T-rails the right shape (no clipping, no overlapping)?
- Cross-section: SiO₂ cladding above LTOI, metal floating on top? No
  geometry leaking into the PML region?

If anything looks wrong, fix and re-preview before paying for a sim.

### Step 6 — DRC

```
python drc.py
```

- DRC PASSED → simulate.
- DRC FAILED → fix the offending knob, re-preview, re-DRC. **Do not
  submit a sim until DRC passes.**

### Step 7 — Simulate

```
python simulate.py --description "<one-sentence summary>"
```

This:
1. Re-renders `output/preview.png`.
2. Submits the TCM (≈ 8 min wall time, ≈ 3.5 FlexCredits at the baseline
   `N_PERIODS = 20` and `MIN_STEPS_PER_WVL = 12`).
3. Extracts α(f), n_eff(f), Z₀(f) from S-parameters via the uniform-line
   method (`tools/_line_extract_from_S21` for α/n_eff, NRW guarded for
   Z₀).
4. Fits `α₀` over 5–50 GHz.
5. Computes the scalar FOM.
6. Archives the run into `output/experiments/NNNN/` (frozen `design.py`,
   `preview.png`, `segmented_summary.png`, `results.json`).
7. Appends one row to `output/results.tsv`.
8. Appends a journal stub to `output/journal.md` for you to fill in.
9. If FOM improved over the previous best, copies `design.py` to
   `output/best_design.py`.
10. Refreshes `output/dashboard.html`.

### Step 8 — Analyze

Inspect `output/segmented_summary.png`:
- |S11|, |S21| traces clean? Bell curve for |S11|? |S21| smoothly above
  ~0.85? If |S21|>1 across most of the band, something is broken.
- α(f) curve smooth? Skin-loss fit (red dashed) tracks well in 5–50 GHz?
- n_eff(f) flat from ~10 GHz onward (slow-wave plateau)?
- Re(Z₀)(f) flat in mid-band? Where does it cross 50 Ω if at all?

### Step 9 — Log

Open `output/journal.md` and fill in the latest stub:
- **Hypothesis**: what you predicted.
- **Result**: actual numbers.
- **vs previous best**: ΔFOM, sign of each knob's effect (was the
  prediction right?).
- **Kept or discarded**: KEPT if FOM improved, DISCARDED otherwise.
- **Lesson**: ONE sentence — be honest about surprises.

### Step 10 — Decide

The framework already promotes the new design to `best_design.py` if FOM
improved. If FOM was worse or equal, **revert**:

```
python -c "from tools.journal import revert_to_best; revert_to_best()"
```

This copies `output/best_design.py` back over `design.py`, ready for the
next iteration.

### After 50 experiments

Print a summary:
- Best FOM and which experiment produced it.
- Best (α₀, Z₀, n_eff) point on the tradeoff curve.
- Topology family that worked best.
- Suggestions for further improvement (e.g., asymmetric T-rails, defected
  ground, multi-period stacking).

---

## 5. Design principles for ultra-low-loss, velocity-matched CPW

Use these as priors when forming hypotheses. They are NOT laws — verify
each in the data.

### How each knob moves each metric (first-order)

| Knob ↑ | α₀ | Z₀ | n_eff |
|---|---|---|---|
| `T_R` (T-top length) | ≈ ↓ (more conductor area) | ↓ | ↑ |
| `T_S` (T-top width) | ↓ slightly | ↓ slightly | ↑ slightly |
| `T_H` (neck extension) | ↑ (current crowding) | ↓ | ↑ ↑ (most leverage) |
| `T_T` (neck width) | ↓ (better DC return) | ≈ | ≈ |
| `T_C` (gap between Ts) | ≈ | ↑ | ↓ (fewer Ts/length) |
| `G` (residual gap) | slight ↑ | ↑ | ↓ (less host C) |
| `WS` (signal width) | ↓ | ↓ | slight ↓ |
| `WG` (ground width) | ↓ slight | slight ↑ | ≈ |
| `TM` (metal thickness) | ↓↓ (skin-effect) | ≈ | ≈ |
| `TSIO21` (cladding gap) | ≈ | ↑ slightly | ↓ slightly (less LTOI overlap) |

### Strategy

The baseline already has reasonable α₀ (0.57) and reasonable Z₀ (39 Ω);
**the biggest opportunity is to push n_eff up by 0.18 toward 2.20 without
crashing Z₀**. T-rails are capacitive loading: more loading → higher
n_eff but lower Z₀. To raise BOTH n_eff and Z₀ you need to add **inductance
preferentially** — that's what T-neck shape, ground-rail patterning, and
metal thickness can do.

Suggested phases (you may deviate when the data tells you to):

- **Phase 1, exps 2–10 — Establish gradients.** One-knob-at-a-time
  perturbations (±25 %) for `T_R`, `T_H`, `T_C`, `G`, `TM`. Build a
  mental model of the response surface from the data.
- **Phase 2, exps 11–20 — Push n_eff toward 2.20.** Increase loading via
  combinations of (`T_R ↑`, `T_H ↑`, `T_C ↓`). Watch Z₀; if it drops
  below ~30 Ω the FOM penalty dominates.
- **Phase 3, exps 21–30 — Recover Z₀ to 50 Ω.** Add inductance:
  thicker metal (`TM`), narrower signal (`WS`), wider gap (`G` ↑) — the
  last hurts n_eff so this is a 2-D search.
- **Phase 4, exps 31–40 — Reduce α₀.** Thicker metal, wider T-tops, look
  at where the surface current peaks in the field plot. Verify the
  α-vs-n_eff Pareto on the dashboard is moving in the right direction.
- **Phase 5, exps 41–50 — Best-of-breed fine tuning.** Small (±5 %) sweeps
  on the best-FOM design; explore one or two qualitatively different
  topologies (e.g., very thin metal but very wide T-tops; or large
  `TSIO21` to shift n_eff downward & let `T_H` push it back up).

### Cost control

A baseline 3-D run is ~8 min wall and ~3.5 FlexCredits. To explore more
cheaply during Phase 1, you may temporarily set `N_PERIODS = 10` (cuts
sim length in half → ~half the cost). Restore to 20 before logging the
final-best design so the headline numbers are comparable to the baseline.

---

## 6. Preview / DRC checklist

Run preview.py + drc.py BEFORE every simulate.py. Fix every visual
anomaly before paying for a sim.

1. **All structures present** — top view shows the segmented section
   between conventional CPW input/output pads; no clipping at edges.
2. **T-rails in pairs** — 4 T's per row (left-ground, signal-left,
   signal-right, right-ground anchors), `N_PERIODS+1` rows.
3. **Rib waveguide visible** in the active gap (cross-section).
4. **DRC passes** — geometric + process rules in `drc.py`.
5. **Source / port amplitudes** — the simulate output should NOT include
   "Source amplitude is not sufficiently large throughout the specified
   frequency range" beyond the band edges. If the warning appears in the
   middle of the band, your geometry is degenerate.

---

## 7. Logging

`output/results.tsv` is structured (one row per experiment). Columns
include `FOM`, `alpha_0_dBcm_per_sqrtGHz`, `alpha_at_Fref_dBcm`,
`Z0_real_at_Fref`, `n_eff_at_Fref`, all eleven design knobs, plus
`wall_time_s` and `description`.

`output/journal.md` is your long-term memory. Entries follow the
auto-generated stub:

```markdown
## Experiment N — <topology tag>

- **Timestamp**: ...
- **Knobs**: T_S=…, T_R=…, ...
- **Hypothesis**: what you predicted and why
- **Result**: actual FOM/α₀/Z₀/n_eff
- **vs previous best**: ΔFOM, signs of effects
- **Kept or discarded**: KEPT / DISCARDED
- **Lesson**: one honest sentence (especially when surprised)
```

---

## 8. Crash handling

| Situation | Action |
|---|---|
| `drc.py` fails | Fix the knob, re-preview, retry. Do not edit `drc.py`. |
| TCM build error | Check the geometry knob you just changed (typo, negative value). |
| Tidy3D server error | Wait 30 s, retry once. If it still fails, log "crash" status and revert. |
| Source-amplitude warning across the whole band | Geometry is degenerate (probably zero-area metal somewhere). Revert. |
| α₀ comes out negative or n_eff > 10 | Extraction unstable — usually means the segmented section is too short or |S21| ≈ 1 everywhere. Increase `N_PERIODS` or revert. |
| FOM < −10 | Almost certainly an extraction artifact, not a real design. Revert. |

---

## 9. Strategy tips

- **One knob per experiment** in Phase 1 — this is what builds the
  first-order gradient table that makes Phase 2+ efficient.
- **Two-knob perturbations** in Phase 2+ — once you know each knob's
  sign of effect, push two together to compensate (e.g., `T_H ↑` AND
  `WS ↑` to raise n_eff while holding Z₀).
- **Don't blow the budget on Phase 1.** Use `N_PERIODS = 10` if needed.
- **Trust the dashboard.** The α-vs-n_eff scatter is the central plot —
  the agent's job is to push points down-and-right of the baseline.
- **Watch the lesson column.** Three "expected n_eff ↑, got n_eff ↓"
  in a row means your mental model of the response surface is wrong;
  fix it before continuing.

Good luck. The first experiment is locked in. Open
`output/dashboard.html` in a browser, then start at experiment 2.
