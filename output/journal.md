# Photonic Bend Design Journal

**Target:** maximize mode transmission through a 90° SiN bend at R=12 µm.
Baseline expectation: circular bend with abrupt curvature transition suffers from mode mismatch at the straight↔curved junctions (bent mode is shifted outward) plus bend radiation.

# Phase 1: Baseline

## Experiment 1 — Baseline circular bend

- **Hypothesis:** Establish baseline with simple circular arc from (0,0) to (12,12).
- **Key parameters:** bend_type=circular, 128 arc points, full width 1.2 µm.
- **Result:** metric = 0.8996 (transmission, higher is better).
- **vs. previous best:** baseline.
- **Kept or discarded:** KEPT.
- **Lesson learned:** Field plot shows classic bent-mode outward shift → mode mismatch at junctions plus some inner-sidewall radiation. ~10 % loss leaves headroom.

# Phase 2: Euler (clothoid-arc-clothoid) bend

## Experiment 2 — Euler bend p=0.5

- **Hypothesis:** Replacing abrupt curvature step (straight → R=12 arc) with a clothoid-arc-clothoid shape where curvature ramps linearly at both ends should reduce mode-mismatch loss at junctions.  p=0.5 means half of the 90° is clothoid, half is a central R=8.5 µm arc.
- **Key parameters:** p_euler=0.5, R_min=8.47 µm in central arc, L=19.96 µm.
- **Result:** metric = 0.9273.
- **vs. previous best:** +0.0276 (improved).
- **Kept or discarded:** KEPT.
- **Lesson learned:** Curvature-continuous Euler bend beats pure circular by ~3 %. The field plot shows less fringing near the junctions. Tighter central R (~8.5) did not noticeably radiate — room to explore larger-p variants.

## Experiment 3 — Euler bend p=0.3

- **Hypothesis:** Less clothoid, more circular arc — keeps central radius larger (9.64 µm) at the cost of a shorter adiabatic transition.
- **Key parameters:** p_euler=0.3, R_min=9.64 µm.
- **Result:** metric = 0.9254.
- **vs. previous best:** -0.0019 (worse).
- **Kept or discarded:** DISCARDED.
- **Lesson learned:** Too little clothoid reduces the benefit of adiabatic curvature transition; the junction mismatch loss dominates the radiation gain.

## Experiment 4 — Euler bend p=0.7

- **Hypothesis:** Push further toward full-Euler — longer clothoids, tighter central R (=7.53 µm).
- **Key parameters:** p_euler=0.7, R_min=7.53 µm.
- **Result:** metric = 0.9133.
- **vs. previous best:** -0.014 (worse).
- **Kept or discarded:** DISCARDED.
- **Lesson learned:** p=0.7 makes the central radius too tight for SiN; bend radiation dominates the mismatch improvement. Confirm p=0.5 is near the peak; try p=0.4 next to home in.

## Experiment 5 — Euler bend p=0.4

- **Hypothesis:** Interpolate between p=0.3 (0.9254) and p=0.5 (0.9273) — expect peak near p=0.4-0.5.
- **Key parameters:** p_euler=0.4, R_min=9.03 µm.
- **Result:** metric = 0.9287.
- **vs. previous best:** +0.0014 (improved).
- **Kept or discarded:** KEPT.
- **Lesson learned:** p=0.4 is slightly better than p=0.5; optimum is in [0.4, 0.5]. Next: combine Euler base with a width taper (wider in the middle) to better match bent-mode profile and allow a tighter effective central radius without radiation.

# Phase 3: Euler + width taper

## Experiment 6 — Euler p=0.4 + sin² width taper, w_ratio=1.3

- **Hypothesis:** Widening the waveguide in the middle of the bend (smoothly via sin²(πu)) increases mode confinement where curvature is largest, reducing outer-sidewall radiation.  Width returns to 1.2 µm at ends so no mismatch with I/O.
- **Key parameters:** p_euler=0.4, w_ratio=1.3 (peak W=1.56 µm), sin² taper.
- **Result:** metric = 0.9314.
- **vs. previous best:** +0.0028 (improved).
- **Kept or discarded:** KEPT.
- **Lesson learned:** Width taper helps; the bent mode prefers a wider guide.  Explore w_ratio range and see if it saturates or keeps improving.

## Experiment 7 — Euler p=0.4 + w_ratio=1.5

- **Hypothesis:** Larger width multiplier may further suppress bend radiation.
- **Key parameters:** w_ratio=1.5 (peak W=1.8 µm).
- **Result:** metric = 0.9297.
- **vs. previous best:** -0.0017 (worse).
- **Kept or discarded:** DISCARDED.
- **Lesson learned:** Too wide excites multimode in the middle → conversion loss back to single-mode at the exit. Optimum w_ratio is near 1.2-1.3.

## Experiment 8 — Euler p=0.4 + w_ratio=1.2

- **Hypothesis:** Home in between 1.1 and 1.3.
- **Key parameters:** w_ratio=1.2 (peak W=1.44 µm).
- **Result:** metric = 0.9315.
- **vs. previous best:** +0.0001 (marginal).
- **Kept or discarded:** KEPT.
- **Lesson learned:** Peak w_ratio ≈ 1.2 (very flat minimum). Further width tuning likely saturating.

## Experiment 9 — Euler p=0.4 + w_ratio=1.1

- **Hypothesis:** Check lower width multiplier.
- **Key parameters:** w_ratio=1.1.
- **Result:** metric = 0.9313.
- **vs. previous best:** -0.0003 (worse).
- **Kept or discarded:** DISCARDED.
- **Lesson learned:** Width taper plateau confirmed around 1.15-1.25. Shift strategy: try asymmetric width growth (more on outer side only) to track bent-mode centroid shift.

## Experiment 10 — Outward radial offset 0.1 µm

- **Hypothesis:** Shift centerline outward to track bent-mode centroid.
- **Result:** metric = 0.9214 (worse by -0.0101). DISCARDED.
- **Lesson learned:** Outward offset hurts for our Euler+taper design.

## Experiment 11 — Asymmetric outer bump

- **Hypothesis:** Grow only outer edge to match the bent-mode without exciting multimode.
- **Result:** metric = 0.9192. DISCARDED. Symmetric widening is strictly better.

## Experiment 12 — p=0.5 + w=1.25

- **Result:** 0.9308. DISCARDED (plateau).

## Experiment 13 — sin² curvature profile

- **Hypothesis:** C∞ curvature.
- **Result:** 0.8523. DISCARDED. Profile had R_min≈4 µm — too tight, radiation dominant.

## Experiment 14 — Euler p=0.45 + w=1.2

- **Result:** 0.9322 (+0.0006). **KEPT**. Fine-tuning p.

## Experiments 15-17 — w sweep around p=0.45

- w=1.25 (0.9319), w=1.15 (0.9321), p=0.48 (0.9320). Plateau confirmed. All DISCARDED.

# Phase 4: Inward radial offset — the breakthrough

## Experiment 18 — Inward offset -0.1 µm

- **Hypothesis:** Opposite direction from exp 10 — maybe inward is what helps.
- **Result:** metric = 0.9417 (**+0.0095**). KEPT — large unexpected jump.
- **Lesson learned:** Inward-bowed centerline (toward bend center) works dramatically better. Likely reason: shifting the waveguide inward relaxes the effective curvature of the long bend path (makes it gentler on average) and improves junction mode matching, while the wider middle compensates for the tighter midpoint curvature.

## Experiments 19-24 — offset sweep at p=0.45, w=1.2

- offset=-0.2 → 0.9495; -0.3 → 0.9553; -0.5 → 0.9602; -0.55 → 0.9600; -0.65 → 0.9581; -0.8 → 0.9503. Peak at ~-0.5.

## Experiments 25-27 — Joint tests

- p=0.3 (0.9249), p=0.6 (0.9600), p=0 pure-circular (0.8572). All DISCARDED.
- **Lesson learned:** Inward offset needs an Euler base — on a pure circular arc it hurts. Width + offset and Euler base are all synergistic.

# Phase 5: Joint width + offset scaling

## Experiments 28-39 — w and offset pushed together

| Exp | w | offset | T | |
|-----|-----|--------|-----|---|
| 28 | 1.4 | -0.5 | 0.9658 | KEPT |
| 29 | 1.6 | -0.5 | 0.9659 | KEPT |
| 31 | 1.6 | -0.7 | 0.9719 | KEPT |
| 33 | 1.6 | -0.8 | 0.9706 | DISC |
| 34 | 1.8 | -0.8 | 0.9728 | KEPT |
| 35 | 2.0 | -1.0 | 0.9734 | KEPT |
| 37 | 2.2 | -1.1 | 0.9684 | DISC |
| **38** | **2.0** | **-1.1** | **0.9751** | **KEPT** |
| 39 | 2.0 | -1.2 | 0.9712 | DISC |

- **Lesson learned:** With more width the mode tolerates larger inward bow. Joint optimum is w≈2, offset≈-1.1.

## Experiments 40-50 — Fine-tuning and sanity checks

- Swept p, shape of offset profile, and small (w, offset) neighbourhoods; none exceeded exp 38.
- sin¹ offset profile (exp 43) and sin⁴ (exp 47) both broke endpoint smoothness → huge losses.
- sin²-shape for both width and offset is critical (smooth endpoint derivative).

# Final Summary

- **Best design:** Euler (clothoid-arc-clothoid) base with p_euler=0.45, symmetric sin² width taper with w_ratio=2.0 (peak width 2.4 µm), and sin² inward radial offset with peak shift r_offset=-1.1 µm.
- **Best metric:** T = 0.9751 (≈ 0.11 dB insertion loss).
- **Improvement vs baseline circular:** +0.0755 (baseline was 0.8996, i.e. ≈0.46 dB → 0.11 dB).
- **Winning strategy:** Stacked three cooperative techniques — (i) curvature-continuous Euler entry/exit kills junction mode-mismatch, (ii) symmetric midpoint widening improves bent-mode confinement, (iii) inward centerline bow relaxes the average effective curvature and keeps mode centered on the wider guide.  Keeping all three profile functions as sin²(πu) (zero and zero-derivative at endpoints) is essential to avoid creating kinks that excite reflection/radiation.
- **Further improvement ideas:** (a) two-structure design — a low-index buffer on the outer sidewall; (b) full topology optimization (freeform level-set) could likely push below 1% loss; (c) parameterize inner and outer edges separately with independent sin² profiles instead of symmetric width + centerline shift.
