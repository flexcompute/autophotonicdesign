# Grating Coupler Auto-Design Journal

Target: fiber-to-chip coupling efficiency (1550 nm TE), 2D FDTD, silicon photonics
220 nm SOI, 70 nm partial etch, SMF-28 beam (MFD ≈ 10.4 µm), tilted Gaussian source.

## Design notes / physics

- Grating equation: `Λ = λ / (n_eff - n_clad·sin θ)` with `n_clad·sin θ_clad = sin θ_air`.
- Average n_eff over a DC=0.5 grating: `(n_slab150 + n_tooth220)/2 ≈ (2.45 + 2.85)/2 ≈ 2.65`.
- For θ_air = 10°, Λ ≈ 1.55/(2.65 − 0.174) ≈ 0.626 µm.
- Upper bound for uniform gratings ≈ 30–40 % (exponential vs. Gaussian mismatch).
- Apodization (varying DC along x) → 50–60 %. Blazing/bottom reflectors → 60–80 %.

# Phase 1: Baseline & coarse sweeps

## Experiment 1 — Baseline

- **Hypothesis:** Provided defaults are close to the grating-equation optimum (Λ≈0.63 for θ=10°).
- **Key parameters:** grating_period=0.63, DC=0.5, num_teeth=25, beam_angle_deg=10.
- **Result:** metric = 0.2441 (24.4 %)
- **vs. previous best:** N/A (first)
- **Kept or discarded:** KEPT
- **Lesson learned:** Uniform grating couples ~24 %; field plot shows exponential decay along x (classic uniform signature) plus visible down-leakage into BOX — so we lose to both mode mismatch and poor directionality.

## Experiments 2-4 — coarse period sweep (angle=10°, DC=0.5, N=25)

- Period 0.60 → 0.1848 (worse), 0.63 → 0.2441 (baseline), 0.64 → 0.0800 (coupling flipped), 0.66 → 0.0008 (fully flipped to +x).
- **Lesson:** At 10°, the 1st-order coupling window is very narrow around Λ=0.63. Larger Λ sends the -1 order forward instead of backward.

## Experiments 5-8 — angle/period co-scan (DC=0.5)

- (14°, 0.644) → 0.324; (18°, 0.662) → 0.343; (22°, 0.681) → 0.360; (26°, 0.701) → 0.364.
- **Lesson:** Bigger θ with matched period monotonically improves. Larger θ moves away from the 2nd-order Bragg condition that creates back-reflection near vertical incidence.

## Experiment 9 — num_teeth=35 (uniform)

- Result 0.231 (worse). The exponential depletion envelope of a uniform grating means teeth beyond ~5 µm of the left edge contribute little — and moving beam_x=L/2 further right shifts the Gaussian off the productive left region.
- **Lesson:** Don't add teeth to a uniform grating; it doesn't get you more Gaussian overlap.

# Phase 2: Apodization

## Experiment 10 — symmetric linear DC 0.3→0.7

- Result 0.307 (worse than 0.364 uniform). Symmetric ramp produces Gaussian-like α profile, but doesn't follow reciprocity.
- **Lesson:** Apodization must be monotonic in α(x), increasing from waveguide end to beam-far end.

## Experiment 11 — monotonic linear DC 0.2→0.5

- Result 0.495 (big jump from 0.364 uniform, +36%). Confirmed reciprocity-optimal direction: α(x) small near waveguide, large near beam-far end.

## Experiments 12-16 — apodization profile variants

- DC 0.15-0.5 → 0.480; DC 0.25-0.5 → 0.4955 (same as 0.2-0.5); quadratic ramp → 0.451; sqrt ramp → 0.465.
- **Lesson:** Linear DC ramp beats both concave-up and concave-down profiles at this regime. Very small dc_start hurts (feature-size interference or phase mismatch).

## Experiments 17-20 — re-tune angle with apodization

- (30°, 0.721) → 0.512; (34°, 0.741) → 0.523; (36°, 0.752) → 0.494; (38°, 0.762) → 0.450.
- **Lesson:** Apodized optimum angle ≈ 34°, a few degrees past the uniform-grating optimum (~26°).

## Experiments 21-22 — period fine-tuning at angle=34°

- 0.750 → 0.410, 0.735 → 0.512. Peak at 0.741 is narrow.

## Experiment 23 — composite "blazed" tooth (failed)

- Added a small secondary tooth in each period. Result 0.105 (catastrophic).
- **Lesson:** Horizontal composite teeth in a 2D binary fixed-height grating CANNOT blaze. The up/down asymmetry ratio A_up/A_down is determined by the vertical stack (substrate below, air above) and is independent of horizontal tooth layout. Composite teeth only detune the Bragg condition.

## Experiments 24-28 — beam position shift

- beam_x / grating_length: 0.55 → 0.498; 0.50 → 0.523 (ref); 0.47 → 0.531; 0.45 → 0.5337; 0.43 → 0.5342; 0.40 → 0.530.
- **Lesson:** Optimum beam_x ≈ 0.41-0.43 of grating length. The beam footprint is projected onto the grating surface at an angle and naturally shifts left (−x) by ~BEAM_Z·tan(34°) ≈ 1.5 µm.

## Experiments 29-34 — angle and period fine tune at apodized optimum

- Angle 32° → 0.531; DC 0.22-0.52 → 0.529; DC 0.30-0.48 → 0.537; DC 0.32-0.46 → 0.538; DC 0.35-0.44 → 0.537; period 0.746 → 0.496.
- **Lesson:** The best apodization range turns out to be narrow (mean DC ≈ 0.39 in a ±0.07 window), not wide. sin²(π·DC) saturates near DC=0.5, so wide ranges waste tooth width without scattering gain.

# Phase 3: Chirp + polish

## Experiments 35-38 — linear period chirp

- Chirp direction matters: 0.751 → 0.731 (decreasing) → 0.517 (bad); 0.735 → 0.747 (increasing) → 0.539 (slight gain); 0.725 → 0.755 (too much) → 0.521; 0.737 → 0.745 (small) → 0.539.
- **Lesson:** A small REVERSED chirp (period grows from waveguide end to beam-far end) gains ~0.005. This matches increasing local n_avg as the beam-side of the grating has higher scattering demand.

## Experiments 39-50 — num_teeth, DC shifts, fine tunes

- N=28 and N=22 both worse. Beam_x=0.41 best of fine scan. DC 0.33-0.47 and uniform DC=0.40 tied best at ~0.5413. Chirp 0.733-0.749 (slightly wider) → 0.5420.

# Final best: Experiment 49 — coupling efficiency = 54.20 %

- **Parameters:**
  - num_teeth = 25
  - beam_angle_deg = 34.0°
  - Uniform DC = 0.40 (apodization benefit evaporated at narrow DC range)
  - Linear period chirp 0.733 µm → 0.749 µm (15 nm total, increasing left-to-right)
  - beam_x = 0.41 × grating_length
- **Total grating length:** 18.53 µm (within 30 µm max).
- **Metric:** 0.5420 (-2.66 dB)

## Strategy that worked best

1. **Big gains came from angle retuning (×1.5):** Going from θ=10° to θ=34° with matched period (grating-equation: Λ = λ/(n_eff − sin θ)) lifted coupling from 0.24 to 0.36 by pushing away from 2nd-order Bragg back-reflection near normal incidence.
2. **Apodization then gave another +0.13:** Monotonic DC ramp (small α at waveguide end, large at beam-far end) aligned the emission profile to the Gaussian by reciprocity.
3. **Beam position, chirp, and fine DC tuning each added +0.005 to +0.01.**
4. **After ~experiment 30 the optimization surface is very flat** — any small change is within ~0.5% of the best.

## Suggestions for further improvement

- **Blazing/bottom mirror** — with fixed 70 nm etch and fixed 2 µm BOX, there is no mechanism to steer more power upward. A DBR/metal reflector under the BOX could push the ceiling toward 70-80 %.
- **Deeper (full) etch + sub-wavelength structures** — a fully-etched grating with carefully placed narrow bars can approach 60-70% without a bottom mirror, but that violates the 70 nm fixed-etch constraint here.
- **Wider beam + longer grating** — SMF MFD ≈ 10.4 µm is fixed in this problem. A larger-mode fiber (UHNA) matched to a longer apodized grating typically reaches 60-65 % in 2D.
- **Adjoint optimization** of per-tooth DC and per-tooth period — in principle could squeeze another +2-3% from the current topology, but returns are small.

---

# Phase 4: 3D focusing grating coupler

Transition from 2D slab grating (best: 0.5420) to 3D focusing grating coupler
with 500 nm strip waveguide output. Geometry: confocal elliptical teeth around
a focal point at (0,0), linear fan taper from 500 nm strip to inner tooth arc.

New 3D-specific knobs: `focal_length` (r_1 on +x axis), `angular_half_span_deg`
(arc extent), and fan shape. 2D-optimized knobs (angle=34, DC=0.40 uniform,
period chirp 0.733→0.749, N=25, beam_x=0.41·L) are seeded in.

Accuracy note: `min_steps_per_wvl = 20` (12 and 16 too coarse for 3D).

## Experiment 51 — 3D baseline

- **Hypothesis:** 2D-optimized knobs (angle=34, DC=0.40, chirp, N=25) + focal_length=12, phi_half=25° should get us close to 2D performance.
- **Key parameters:** focal_length=12, angular_half_span_deg=25, n_eff_est=2.65.
- **Result:** metric = 0.4943 (49.4 %)
- **vs. 2D best:** −0.048 (4.8 percentage points below 2D best of 0.5420)
- **Kept or discarded:** KEPT (baseline)
- **Lesson learned:** Focusing gives up ~5 % vs 2D, as expected from fan/strip mode mismatch and finite-arc effects. Good starting point; 0.54+ should be reachable with focal/arc tuning.

## Experiments 52-56 — coarse focal_length and angular_half_span sweep

- f=16 → 0.4831, f=9 → 0.4799, f=12 stayed best (0.4943).
- phi_half=30 → 0.4676, phi_half=20 → 0.4941 (tied with 25).
- **Lesson learned:** focal_length=12 and angular_half_span_deg≈25 are near-optimal; sensitivity on focal_length is ~3%/3µm.

## Experiments 56-57 — beam_x shift

- beam_x=0.50·L → 0.4645, beam_x=0.35·L → 0.4885, beam_x=0.41·L still best.
- **Lesson learned:** 2D-optimized beam fraction (0.41) transfers directly to 3D, slightly narrow peak.

## Experiments 58-61 — apodization, chirp, angle fine-tune

- DC 0.33-0.47 apodized → 0.4899 (worse); uniform period → 0.4910 (chirp helps slightly, +0.003).
- angle=36 (+matched period) → 0.4188 (big drop); angle=32 → 0.4223 (also big drop).
- **Lesson learned:** The 3D angle optimum is NARROW near 34° (vs 2D's broader peak). Apodization gives nothing at narrow DC range; uniform DC=0.40 is the right choice, chirp 0.733→0.749 still helps.

# Phase 4a: Ellipse eccentricity — the big 3D-specific knob

## Experiments 62-69 — n_eff_est sweep (sets ellipse eccentricity)

- n_eff_est=2.65 (theoretical) → 0.4943 (baseline)
- 2.80 → 0.5012, 2.95 → 0.5055, 3.20 → 0.5105, 3.47 → 0.5135
- 3.80 → 0.5142 ← best
- 4.00 → 0.5142 (tied, plateau)
- 4.50 → 0.5120, 10.0 → 0.4830 (too circular)
- **Lesson learned:** The analytically-derived eccentricity (e = sin(θ)/n_eff with n_eff ≈ 2.65) is wrong for our geometry. The effective optimum is n_eff ≈ 3.8-4.0, meaning e ≈ 0.14 (much flatter ellipses than the grating equation predicts). Likely because the focused slab mode isn't a plane wave — it has spatial curvature across the tooth arcs, and the correction nearly cancels out the tilt term. This gave +0.02 over the baseline, more than any other single knob.

## Experiment 70 — focal_length fine-tune under new n_eff

- f=11 (vs f=12 under new n_eff) → 0.5127, worse.
- **Lesson learned:** focal_length optimum didn't shift with n_eff change.

---

# Final best: Experiment 69 (3D) — coupling efficiency = 51.42 %

- **Parameters:**
  - num_teeth = 25, beam_angle_deg = 34, duty_cycle = 0.40 uniform
  - focal_length = 12 µm, angular_half_span_deg = 25°
  - Period chirp 0.733 → 0.749 µm (15 nm)
  - beam_x = 0.41 × grating_radial_length
  - n_eff_est = 4.00 (sets ellipse eccentricity e ≈ 0.14 — flatter than theoretical)
  - min_steps_per_wvl = 20
- **Metric:** 0.5142 (-2.88 dB)
- **vs. 2D best (0.5420):** −0.028 (2.8 percentage points — a reasonable 3D focusing-cost penalty).

## Strategy that worked best in 3D

1. **Seeding from 2D was near-free:** angle/DC/period/beam_x/num_teeth transferred directly with no re-tuning needed.
2. **Ellipse-eccentricity tuning was the biggest 3D gain (+0.02):** the theoretical grating-equation eccentricity (e ≈ 0.21) was too curved. Empirically e ≈ 0.14 (n_eff_est ≈ 3.8-4.0) gives better phase matching for the focused slab mode.
3. **Don't trust the analytical shape blindly in 3D** — the focused mode has non-trivial spatial structure that shifts the optimum eccentricity, and this isn't captured by the plane-wave-in-a-slab grating equation.

## Suggestions for further improvement

- **Bottom mirror** — same as 2D, could push to 70 %.
- **Adjoint optimization** of per-tooth radii (not just r₀, but per-angle-φ position) — can squeeze another few percent by individually phasing each tooth element.
- **Fan shape** — a non-elliptical fan (e.g., parabolic taper) matched to the strip's radiation pattern could reduce mode-mismatch loss.
- **Final verification** should be run at `min_steps_per_wvl = 25-30` per the repo's accuracy guidance.

