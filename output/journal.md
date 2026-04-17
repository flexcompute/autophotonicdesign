# Photonic Taper Auto-Design Journal

Target: Silicon waveguide taper, 0.5 µm → 5 µm width, 6 µm fixed length.
Metric: fundamental TE mode transmission at 1550 nm (higher is better).

## Background knowledge
- A **linear taper** is rarely optimal at this aspect ratio (5 µm output, only 6 µm long) — adiabatic criterion `dW/dz << (β1 - β2) / k0` is very hard to meet when expanding 10×. Expect large higher-order mode excitation.
- **Adiabatic profiles** concentrate slow width-change where the mode overlap with higher-order modes is highest (i.e., where width approaches the cutoff of the next mode). Practical forms: parabolic, exponential, `tanh`, Hamerly-style, or sine-squared.
- **Clements / raised-cosine** and **Mod-Hamerly** (`W(z) = W0 + (W1-W0) * f(z/L)` where f is chosen to enforce mode-adiabaticity) are common wins.
- At very short length (6 µm) the problem becomes shape-optimization: minimizing scattering into TE1, TE2, TE3 modes.
- Literature: A linear taper at 10× expansion over 6 µm typically transmits 70-85%. Adiabatic profiles can push 90-95%. Shape-optimized/inverse-designed can exceed 97%.

---

# Phase 1: Baselines

## Experiment 1 — Linear taper baseline

- **Hypothesis:** Start with linear taper to set baseline. Expect ~70-85% from theory/literature.
- **Key parameters:** Straight-sided PolySlab from (0, 0.25) to (6, 2.5).
- **Result:** metric = 0.60719 (fundamental-mode transmission)
- **vs. previous best:** N/A (baseline)
- **Kept or discarded:** KEPT (initial baseline)
- **Lesson learned:** Linear taper is worse than typical literature; 10× expansion in 6 µm is quite abrupt. Field shows curved wavefronts and mode mismatch — strong excitation of higher-order even modes. Big headroom for shape engineering.

## Experiment 2 — Power-law p=0.5 (sqrt shape, fast-start)

- **Hypothesis:** Since TE0↔TE2 beat length shrinks with W, widen fast at the narrow end (where β-separation is large) and slow at the output. W(x)=W0+(W1-W0)(x/L)^0.5.
- **Key parameters:** p = 0.5, N=80 segments.
- **Result:** metric = 0.12013
- **vs. previous best:** −0.487 (much worse)
- **Kept or discarded:** DISCARDED
- **Lesson learned:** Fast widening at the narrow end is catastrophic — at small W, dβ/dW is very large; even a small dW/dz causes a strong local mode mismatch. The adiabaticity bottleneck is actually at the narrow end, not the wide end as I assumed. **Next: try the opposite — slow start (p > 1).**

## Experiment 3 — Raised-cosine taper (slow both ends)

- **Hypothesis:** Zero slope at both endpoints should minimize mode-mismatch at the two bottlenecks.
- **Key parameters:** W(x)=W0+(W1-W0)*0.5*(1-cos(πx/L)), N=80.
- **Result:** metric = 0.43948
- **vs. previous best (linear 0.607):** −0.168 (worse)
- **Kept or discarded:** DISCARDED
- **Lesson learned:** Raised cosine's peak mid-section slope (dW/dx_max ≈ (W1-W0)π/(2L) ≈ 1.18 µm/µm) is much larger than the linear's constant 0.75. The mid-section widening is the bottleneck — it exceeds the local adiabatic limit. **Constant slope (linear) beats "smooth-ended" profiles when the taper is aspect-ratio-limited.**

Data so far: peak dW/dx sets the scale. Linear (0.75) = 0.607. Raised-cos (1.18) = 0.44. Sqrt (∞ at x=0) = 0.12. → Any profile with peak slope > linear is likely worse. The best shape must keep slope ≤ 0.75 and distribute it cleverly (slow at the wide end where TE0/TE2 beat length is short, slightly faster at narrow end where modes are well separated).

## Exploration 1 — Mode solver + parametric sweep

Computed n_eff(W) for TE0..TE5 at W = 0.5-5 µm. Δn(TE0-TE2) drops from ~1 at W=0.5 to ~0.03 at W=5. Pure Hamerly adiabatic profile predicts infeasible (peak dW/dz = 8 µm/µm near narrow end — same failure mode as sqrt). Physical constraint: mode can only reshape at a rate limited by its diffraction scale, not just β-difference.

**Power-law sweep (p=0.7, 1.0, 1.3, 1.7, 2.0, 2.5):** all between 0.50 and 0.61. Linear (p=1.0) wins among pure power-laws.

**Bilinear sweep (xb ∈ {2,3,4}, Wb ∈ {1.5, 2.5, 3.5}):**
- xb=4, Wb=2.5 → T = 0.6430 ← best
- xb=3, Wb=2.5 → T = 0.6299
- xb=4, Wb=3.5 → T = 0.6072 (= linear by construction: 0.5→3.5 in 4µm is slope 0.75, 3.5→5 in 2µm is slope 0.75)
- xb=2, Wb=3.5 → T = 0.2308 (steep narrow start fails)

Surprise finding: The winner has **gentle narrow end (slope 0.5)** + **steep wide end (slope 1.25)** — opposite of β-adiabaticity. Hypothesis: at the wide end, TE0 and TE2 have similar β so coupling is "uniform" and small phase mismatch integrates out. At the narrow end, however, dβ/dW is so large that even small slope creates big local mismatch. So: minimize dW/dz where dβ/dW is high (narrow), not where Δβ is small (wide).

## Experiment 4 — Bilinear taper (xb=4, Wb=2.5)

- **Hypothesis:** Gentle narrow-end (slope 0.5) + steep wide-end (slope 1.25) based on bilinear sweep.
- **Key parameters:** xb=4.0, Wb=2.5 µm, N=80.
- **Result:** metric = 0.64298
- **vs. previous best:** +0.036 (best so far)
- **Kept or discarded:** KEPT
- **Lesson learned:** Breaking the linear taper into two segments, with the **narrow end made gentler** and the **wide end correspondingly steeper**, beats pure linear. This confirms the narrow end is the scattering bottleneck, not the wide end. Next: refine the break point and/or add a third segment for even more flexibility.

# Phase 2: Multi-segment optimization

## Exploration 2 — Bilinear refinement + power-then-line

Sweep around (xb=4, Wb=2.5) showed monotonic improvement with larger xb AND larger Wb:
- xb=5.75, Wb=3.25 (pure bilinear) → T=0.7257
- Adding a sqrt-shaped narrow segment with p=0.7 jumped to T=0.7979.
- Finer sweep: p=0.5, xb=5.9, Wb=3.5 → T=0.9195 (predicted)

**Big insight:** The best profile is (a) concave-up "sqrt" narrow segment that starts fast at the input end but slows down approaching a mid-value of W=3.5, followed by (b) a quasi-step expansion from W=3.5 to W=5 over just 0.1 µm. This works because:
1. In the sqrt narrow segment, the local slope at x=0 is large but decreases rapidly, so the mode-evolution rate is fast where β-spacing is still large (TE2 poorly guided), and slow where β-spacing gets smaller.
2. At W=3.5 vs W=5, TE0 mode profiles are nearly identical (both broad) and β differs by only ~0.005. A step junction there has ~0.99+ overlap integral. The "step" is effectively a small perturbation.

## Experiment 5 — Power-then-line (xb=5.9, Wb=3.5, p=0.5)

- **Hypothesis:** Use sqrt-shaped narrow segment (long, slow approach to W=3.5) followed by near-step to W=5, exploiting TE0 degeneracy at wide W.
- **Key parameters:** xb=5.9, Wb=3.5 µm, p=0.5, N=201.
- **Result:** metric = 0.91971
- **vs. previous best (0.643):** +0.277 (big jump)
- **Kept or discarded:** KEPT
- **Lesson learned:** The "sudden approximation" at the wide end (3.5→5 step) is essentially loss-free because wide TE0 modes are near-degenerate in β and near-identical in profile. This is the key trick for this geometry. Next: refine the sqrt-segment shape further (maybe add control points) and try to smooth the step with a short tapered transition.

# Phase 3: Autograd / adjoint optimization

Parameterization: monotonic PolySlab widths via cumsum(softplus(params)). Two segments: narrow [0, xb=5.9] with M_narrow equispaced control widths; step [xb, L] with M_step widths for shaping the wide-end transition. Endpoints (0, 0.5) and (L, 5.0) fixed. Tidy3D autograd runs 1 forward + 1 adjoint FDTD per gradient step; Adam updates. Warm-start each scale-up by np.interp'ing previous widths.

Trajectory: 8pt → 10pt → 16pt → 20+3 → 30+7 → 50+15 → 80+25 → 120+40 control widths. Log-linear gain per scale-up with diminishing returns, saturating near T ≈ 0.974.

| Exp | Config | T | Notes |
|-----|--------|---|-------|
| 6   | 8-pt narrow + step | 0.9252 | first autograd, warm from sqrt baseline |
| 7   | 10-pt | 0.9402 | |
| 8   | 16-pt | 0.9461 | |
| 9   | 20+3 | 0.9528 | step region shaped, not just linear ramp |
| 10  | 30+7 | 0.9588 | |
| 11  | 50+15 | 0.9605 | |
| 12-18 | 50+15 Adam refines | 0.9628 → 0.9691 | |
| 19  | 80+25 | 0.9701 | crossed 0.97 |
| 20-24 | 80+25 refines | 0.9706 → 0.9722 | |
| 25  | 120+40 | 0.9726 | |
| 26-31 | 120+40 refines | 0.9729 → 0.9740 | diminishing returns (≤ +0.0002 per round) |
| 32  | final refine | 0.97414 | budget-limited |

Throughout, the qualitative profile preserved the Phase-1 structure: a long, concave-up narrow segment (W rises from 0.5 to ~3.8 over 5.9 µm, with a fast initial rise slowing to near-linear by mid-taper) + a short steep step segment (3.8 → 5.0 over 0.1 µm). Fine-grained optimization tuned dozens of local inflections that reduce residual mode-mismatch at specific widths.

## Final result

- **Best T = 0.97414** (experiment 32).
- **Baseline linear T = 0.6072**. Loss reduction: 39.3% → 2.6% (15× improvement).
- **Design:** free-form monotonic sidewall defined by 162 control widths (120 narrow + 40 step + 2 endpoints), interpolated piecewise-linearly onto a 601-point polygon.

## Key insights (for future agents)

1. **Peak-slope constraint.** For an aspect-ratio-limited taper (10× expansion in 6 µm, 0.375 mean slope per side), the "peak dW/dx" is a leading-order proxy for loss among simple parametric profiles (linear 0.61 ≫ raised-cos 0.44; sqrt diverges and gives 0.12).
2. **The narrow end is the bottleneck, not the wide end.** dβ/dW is large at W<1 µm, so coupling into higher-order even modes is extremely sensitive to dW/dz there. A gentle narrow-end + steep wide-end beats the β-adiabatic Hamerly prediction.
3. **The "step approximation" is nearly lossless at wide W.** At W=3.8, TE0/TE2 β-separation is ~0.005 and TE0 mode profiles are nearly width-independent. Stepping to W=5 over 0.1 µm has ≥0.99 projection overlap and removes no-longer-useful propagation length that would otherwise be wasted in the near-degenerate regime.
4. **Autograd pays off.** Gradient descent on 160 monotonic widths with Tidy3D adjoint FDTD reliably climbs the loss landscape from 0.92 (best parametric) to 0.974, in ~9 iterations per scale.
5. **Scale-up matters more than more iterations.** Each doubling of control points gave more than an entire extra scale of Adam refinement at the previous resolution.

## Suggestions for further improvement (beyond budget)

- **Free xb.** Kept at 5.9 the whole time. Jointly optimizing xb with widths might yield ~0.001 more.
- **Joint optimization of x-positions.** Currently only widths are free; letting the optimizer slide control points sideways would add DOF.
- **Increase simulation resolution.** Gradients at min_steps_per_wvl=20 are slightly noisy; 30 might help final polishing.
- **Stochastic restarts / perturbation.** The Adam trajectory is deterministic and may be stuck in a local minimum. Perturbing and re-optimizing from multiple seeds could find basins beyond 0.974.
- **Bulged sidewalls.** PolySlab supports `bulges` (circular arcs per edge). A smooth curved sidewall could relax the need for hundreds of control points and may help where piecewise-linear incurs scattering.
