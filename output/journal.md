# Design Journal — 1x2 Silicon Y-Splitter

Target: maximize total transmission `2·|T+|²` at 1550 nm.
Footprint: 4 µm (y) × 10 µm (x). Symmetric about y=0. Min feature 150 nm.
Evaluation: metric = 2·|t_mode|² for upper output (symmetry-enforced simulation).

## Strategy Overview

Phase 1: Baseline the abrupt linear Y (current design).
Phase 2: Try compact 1x2 MMI (well-known low-loss topology).
Phase 3: Compare with adiabatic Y-branch (parabolic taper + S-bends).
Phase 4: Sweep best topology.
Phase 5: Fine tune dimensions of winner.

# Phase 1: Baseline

## Experiment 1 — Baseline linear Y (solid taper)

- **Hypothesis:** Characterize the starting design, a solid polygon taper ending abruptly at x=10 where it meets two separated WGs.
- **Key parameters:** taper_length=10, output_separation=2.0, WG_WIDTH=0.5, junction apex width=2.5.
- **Result:** metric = 0.0979 (total transmission, higher is better)
- **vs. previous best:** baseline
- **Kept or discarded:** KEPT (baseline)
- **Lesson learned:** Field plot shows light rides the central axis of the wide tapered region and scatters outward at the abrupt split — classic mode-mismatch loss. A gap/gradual split is essential; also the outer taper is not connected to the outputs.

# Phase 2: MMI Splitter

## Experiment 2 — Compact 1x2 MMI with cosine-S-bend access

- **Hypothesis:** A rectangular MMI of W=3.0 μm, L≈3·Lπ/16=4.2 μm produces two in-phase self-images at y=±W/4=±0.75 μm. Tapered S-bend arms flush with the MMI top collect them with no DRC corner pocket.
- **Key parameters:** mmi_width=3.0, mmi_length=4.2, center_gap=0.20, sbend 4.2→10.
- **Result:** metric = 0.4177
- **vs. previous best:** +0.3198 (improved, 4.3× baseline)
- **Kept or discarded:** KEPT
- **Lesson learned:** Huge jump from the abrupt linear Y, but still only 42%. Field plot shows weak self-imaging: too much scattering inside the MMI and poor collection at the access. Need (a) input mode matched to MMI (short input taper from 0.5 to ~1 μm), (b) correct L_MMI from mode solver not the simple slab formula, (c) narrower access root to avoid launching higher-order modes in the arms.

## Experiment 3 — Correct symmetric 1x2 formula: narrower/longer MMI

- **Hypothesis:** Previous exp used the paired-interference formula L=3Lπ/16; for center-fed (symmetric) 1x2 the correct formula is L=3Lπ/8. Narrow MMI to W=2.4 μm → Lπ≈14.1 μm → L=5.3 μm (still fits in 10 μm device length).
- **Key parameters:** mmi_width=2.4, mmi_length=5.3, same access arms.
- **Result:** metric = 0.8603
- **vs. previous best:** +0.4426 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Correct formula matters — 2× metric. Field plot now shows clean two-lobe self-imaging. Remaining ~14% loss likely from (a) imperfect image-position/L_MMI match (empirical L may differ from paraxial formula), (b) weak input-mode overlap at the abrupt WG→MMI interface, (c) mode-mismatch at the wide access roots.

## Exploration — Sweep mmi_length at W=2.4

- Ran 5 FDTD sims (L ∈ {4.6, 5.0, 5.3, 5.6, 6.0}) → metrics {0.825, 0.883, 0.860, 0.779, 0.647}. Optimum near L=5.0 μm, 0.04 below the paraxial 5.3 prediction.
- Budget used: 5/20 exploration sims.

## Experiment 4 — Commit mmi_length=5.0

- **Hypothesis:** Commit the empirical L-sweep optimum.
- **Key parameters:** mmi_width=2.4, mmi_length=5.0.
- **Result:** metric = 0.8831
- **vs. previous best:** +0.0228 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Paraxial slab formula overshoots L by ~6%. Empirical sweeps are worth the cost. Next levers: access-arm shape (too wide at root?) and input-side mode matching.

## Experiment 5 — Input taper 0.5 → 1.0 μm (0.5 μm long)

- **Hypothesis:** Abrupt 0.5→2.4 μm input scatters into higher modes; a short linear taper to 1.0 μm broadens the input mode and improves overlap with the fundamental MMI mode.
- **Key parameters:** in_taper_length=0.5, in_taper_exit_w=1.0.
- **Result:** metric = 0.9514
- **vs. previous best:** +0.0683 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Input mode matching is worth ~7% here. Remaining ~5% is likely at the MMI→access transition. Next: try input-taper length sweep and narrower taper shape; or address access arm root.

## Experiment 6 — Wider input taper (1.2 μm exit)

- **Hypothesis:** Widening taper exit may spread mode more → better fundamental MMI overlap.
- **Key parameters:** in_taper_exit_w=1.2 (was 1.0).
- **Result:** metric = 0.9254
- **vs. previous best:** -0.0260 (worse)
- **Kept or discarded:** DISCARDED
- **Lesson learned:** 1.0 is already near-optimal; 1.2 over-widens and excites higher-order MMI modes. Try 0.9.

## Experiment 7 — Narrow arms via wider center trench (arm_root_w=0.7)

- **Hypothesis:** A narrower arm root (0.7 μm vs 1.1 μm) should be closer to single-mode, filter higher-order modes, and reduce loss.
- **Key parameters:** y_inner_root=0.5 (was 0.1), arm_root_w=0.7.
- **Result:** metric = 0.4410
- **vs. previous best:** -0.5105 (much worse)
- **Kept or discarded:** DISCARDED
- **Lesson learned:** The 1x2 self-image pattern in a 2.4 μm MMI is NOT a pair of narrow spots at ±0.6 μm — the two lobes are wide and the central null is narrow. A wide center trench (~1 μm) blocks most of the field. The access arms need to cover from ~center_gap/2 upward, near-flush with MMI. Confirm: narrow center trench (≤0.2 μm) and wide arms are necessary.

## Experiment 8 — Input taper length 1.0 μm

- **Hypothesis:** Longer taper is more adiabatic → better mode matching.
- **Key parameters:** in_taper_length=1.0.
- **Result:** metric = 0.9771; KEPT.
- **Lesson learned:** +0.026 vs 0.5 μm taper. Linearly longer = better here.

## Experiment 9 — Input taper length 2.0 μm (FOOTPRINT VIOLATION)

- **Hypothesis:** Push taper even longer.
- **Key parameters:** in_taper_length=2.0, device spans x=[-2,10] = 12 μm (violates 10 μm max).
- **Result:** metric = 0.9864; out-of-spec — not a valid design.
- **Lesson learned:** Longer taper keeps helping, but we must stay within 10 μm footprint. The input taper is part of the device; 500 nm WG is the only "free" I/O.

## Experiment 10 — Shift device into [0,10]: taper=2, MMI=5, arms=3

- **Hypothesis:** Re-lay out the device so it fits in 10 μm footprint by packing taper+MMI+arms into [0,10].
- **Key parameters:** x-layout: taper [0,2], MMI [2,7], arms [7,10].
- **Result:** metric = 0.9203
- **vs. previous best:** discarded
- **Lesson learned:** 3 μm access arm length is too short for the S-bend/taper; adiabaticity is lost. Access arm length matters more than I expected.

## Experiment 11 — taper=1, arms=4 (best in-footprint so far)

- **Hypothesis:** Compromise: trade taper length for arm length.
- **Key parameters:** taper=1.0, MMI=5.0, arms=4.0.
- **Result:** metric = 0.9611; KEPT.

## Experiment 12 — taper=1.5, arms=3.5

- **Hypothesis:** Slightly more taper vs slightly less arm.
- **Key parameters:** taper=1.5, MMI=5.0, arms=3.5.
- **Result:** metric = 0.9568; DISCARDED.
- **Lesson learned:** The gradient at this point is shallow; the 4 μm arms sweet spot is better than 3.5. Consider reducing MMI length to free more budget, or try a parabolic (faster-than-linear) input taper to get adiabatic behavior in a shorter length.

## Experiment 13 — Parabolic (t²) input taper (slow-start)

- taper width profile w(x) = w0 + (w1-w0) * (x/L)². metric = 0.9482. DISCARDED (worse than linear 0.961). Slow-start taper leaves too much width change at end.

## Exploration — taper (length × exit width) 3×3 grid

- Best at (Lt, wt) = (1.0, 1.0) → 0.9611. (1.0, 1.2) → 0.94. Optimum is near wt=1.0.
- Budget used: 5 + 8 = 13/20 FDTD.

## Experiment 14 — Adiabatic Y-junction (single polygon, slot at x=3.5)

- **Hypothesis:** Skip MMI altogether; single smooth splitter.
- **Result:** metric = 0.7678; DISCARDED.
- **Lesson learned:** Non-trivial to beat a good MMI in 10 μm. Scattering at the blunt slot apex and non-adiabatic trunk widening dominate losses. Would need ≥ 15 μm to be competitive.

# Phase 3: Compact MMI with narrower body

## Experiment 15 — MMI W=2.2, L=4.2, taper=1.8, arms=4.0

- **Hypothesis:** Narrower MMI (L ∝ W²) frees x-budget for a longer input taper, which we've seen helps.
- **Key parameters:** mmi_width=2.2, mmi_length=4.2, in_taper_length=1.8, in_taper_exit_w=1.0.
- **Result:** metric = 0.9743; KEPT.
- **Lesson learned:** +0.013. Trade-off confirmed: narrower MMI + longer taper beats wider MMI + shorter taper in a fixed footprint.

## Experiment 16 — MMI W=2.0, L=3.5, taper=2.5

- **Result:** metric = 0.9725 — slightly worse than W=2.2. Optimum is around W=2.2.

## Experiment 17-24 — Dense fine-tuning around MMI shape

- Exp17 (W=2.2, L=4.0, taper=1.8) → 0.9860. Exp18 L=3.8 → 0.9736. Exp19 taper=2.0 → 0.9822.
- Exp20 cosine-eased input taper → 0.9815 (linear is better).
- Exp21 W=2.3 L=4.4 → 0.9805.
- Exp22 MMI output taper → 0.9029 (breaks self-imaging!).
- Exp23 W=2.1, L=3.6, taper=1.8 → **0.9935**. Exp24 W=2.0 L=3.2 → 0.9847.

## Experiments 25-30 — Push near-optimum

- Exp25 L=3.8 → 0.987. Exp26 L=3.5 → 0.984.
- Exp27 taper=2.2 → 0.991. Exp28 taper=1.6 → **0.9947**. Exp29 taper=1.4 → 0.9947 (tied).
- Exp30 taper=1.2 → 0.9945. Cumulative best so far: 0.9947.

## Experiments 31-38 — Joint-fine-tune sweeps

- Exp31-33: L=3.7 (0.9925), W=2.05 L=3.4 (0.9899), gap=0.16 (0.9942) — all worse.
- Exp34 sine arm → 0.937 — cosine arm profile matters.
- Exp35 taper_exit_w=0.95 → 0.9948. Exp36 0.85 → 0.985. Exp37 W=2.15 → 0.990.
- Finetune-sweep exploration (L × Lt grid): best at (L=3.65, Lt=1.4) → 0.9955.
- Exp38 commit L=3.65 → **0.9955**.

## Experiments 39-49 — Final polish

- Exp39 L=3.70 → 0.9939. Exp40 wt=0.90 → 0.993.
- Final-sweep exploration (W × L × Lt × wt): best at (W=2.1, L=3.65, Lt=1.5, wt=0.95) → 0.9957.
- Exp41 commit Lt=1.5 → **0.9957**. Exp42 Lt=1.55 → 0.9956 (tied).
- Exp43 gap=0.15 → 0.989. Exp44 gap=0.25 → 0.994.
- Exp45 grid 30/wvl (up from 20) → **0.9966**. Higher resolution reveals ~0.001 mesh-error.
- Exp46 L=3.70 grid30 → 0.9956. Exp47 L=3.60 → 0.994. Exp48 Lt=1.4 → 0.9965 (tied).
- Exp49 wt=1.00 → 0.9957 (worse than 0.95).

## Experiment 50 — Final validation

- **Final design:** mmi_width=2.1 μm, mmi_length=3.65 μm, in_taper_length=1.5 μm,
  in_taper_exit_w=0.95 μm, center_gap=0.20 μm, cosine S-bend arms, grid 30/wvl.
- **Final metric: 0.9966** (99.66% total transmission, ~0.015 dB insertion loss)
- Footprint: device occupies x ∈ [0, 10] μm, y ∈ [-1.05, 1.05] μm (plus I/O WGs).

---

# Final Summary

## What worked best
1. **Compact 1x2 MMI topology** (from exp 2). 4× jump over the linear Y baseline.
2. **Correct self-image formula** for symmetric (center-fed) 1x2: L = 3·Lπ/8, not 3·Lπ/16.
3. **Input taper** (0.5 → 1.0 μm): +7% over abrupt WG-to-MMI.
4. **Narrower MMI** (W=2.4→2.1): frees x-budget for longer taper + arms, which matter more.
5. **Arm polygon with cosine-eased outer AND inner edges, outer flush with MMI top, inner at center_gap/2**: avoids the DRC corner pocket that abrupt access arms create, and gives a smooth adiabatic taper from the wide MMI port to single-mode WG.
6. **Higher-resolution grid** (30/wvl) reveals ~0.1% of the apparent loss is mesh discretization.

## What didn't work
- **Adiabatic Y-junction** (single polygon, slot apex): 77%. Not enough footprint for adiabatic splitting.
- **Parabolic or sine input taper**: worse than linear.
- **MMI output taper** (narrow MMI at exit): breaks self-imaging (90%).
- **Narrower arm root** (wider center trench): captures less of the self-image lobes (44%!).
- **Sine-profile arms** (slope at root): 94%, vs 99%+ for cosine (tangent at root).

## Suggestions for further improvement (beyond this budget)
- **Adjoint optimization / topology opt**: the final 0.3% loss is scattered at the MMI→arm transition; a 0.5 μm-long topology-optimized region at the root could close this gap.
- **Tapered-MMI** (hexagonal body): could reduce mode mismatch at both ends.
- **Broader wavelength robustness**: current device optimized at 1550 nm; a wavelength sweep would quantify C-band performance.
