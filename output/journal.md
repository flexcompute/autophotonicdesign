# Experiment Journal


## Experiment 1 — Linear inverse taper baseline

- **Hypothesis:** Establish the 180 nm linear inverse taper baseline before topology changes.
- **Result:** metric = 0.7478
- **vs. previous best:** n/a (first experiment)
- **Kept or discarded:** KEPT
- **Lesson learned:** Baseline couples well at metric 0.7478, with a narrow guided beam and visible residual lateral radiation near the facet.

## Experiment 2 — Power-law single inverse taper

- **Hypothesis:** Use a 180 nm tip with a power-law exponent of 1.7 to slow the initial width expansion and reduce tip-mode radiation.
- **Result:** metric = 0.8178
- **vs. previous best:** +0.0700 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Metric improved to 0.8178; the slower facet-side expansion kept the field more tightly guided after initial capture.

## Experiment 3 — Refined power-law taper

- **Hypothesis:** Refine the single inverse taper to a 200 nm tip and exponent 1.85 after local FDTD tuning around the experiment-2 optimum.
- **Result:** metric = 0.8255
- **vs. previous best:** +0.0077 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Metric rose to 0.8255; a slightly wider tip improved net overlap more than the smaller tips while preserving adiabatic transfer.

## Experiment 4 — High-exponent inverse taper

- **Hypothesis:** Retune the single inverse taper to a 210 nm tip and exponent 2.25 after wider-tip/high-exponent sweeps showed a shallow optimum there.
- **Result:** metric = 0.8289
- **vs. previous best:** +0.0034 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Metric improved to 0.8289; failed trident and SWG explorations suggest this stack favors one smooth solid taper over disconnected capture features.

## Experiment 5 — Locally bumped taper profile

- **Hypothesis:** Apply a smooth local profile correction: reduce mid-taper width growth and slightly boost the late taper to delay compression without changing the 210 nm tip.
- **Result:** metric = 0.8354
- **vs. previous best:** +0.0065 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Metric improved to 0.8354; delaying the middle compression while recovering width late reduces radiation better than a pure power law.

## Experiment 6 — Refined delayed-compression taper

- **Hypothesis:** Strengthen the local profile correction to mid_bump -0.34 and late_bump 0.14 after the previous bump optimum sat on the delayed-compression edge.
- **Result:** metric = 0.8395
- **vs. previous best:** +0.0041 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Metric improved to 0.8395; pushing compression later helps until about mid_bump -0.34, after which extra delay rolls over.

## Experiment 7 — Shifted bump centers

- **Hypothesis:** Move the delayed-compression correction later in the taper and shift the late recovery earlier to match the field evolution seen in the refined bump profile.
- **Result:** metric = 0.8416
- **vs. previous best:** +0.0021 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Metric improved to 0.8416; the useful correction is centered later than the original mid-taper guess, while moving it too far later rolls over.

## Experiment 8 — Retuned shifted-bump amplitudes

- **Hypothesis:** Retune the shifted bump amplitudes to mid_bump -0.46 and late_bump 0.18 after moving the correction centers changed the optimum.
- **Result:** metric = 0.8437
- **vs. previous best:** +0.0021 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Metric improved to 0.8437; stronger delayed mid-compression helps, but probes past -0.46 roll over sharply.

## Experiment 9 — Corrected-profile tip and power retune

- **Hypothesis:** Retune the base tip and exponent under the shifted-bump profile, moving to a 200 nm tip and exponent 2.20.
- **Result:** metric = 0.8471
- **vs. previous best:** +0.0034 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Metric improved to 0.8471; after adding delayed-compression bumps, the best facet tip shifts slightly narrower than the earlier 210 nm optimum.

## Experiment 10 — Early facet-side profile correction

- **Hypothesis:** Add a small early negative bump centered at 20 percent of the taper to slightly delay the first width growth under the corrected profile.
- **Result:** metric = 0.8472
- **vs. previous best:** +0.0001 (improved)
- **Kept or discarded:** KEPT
- **Lesson learned:** Metric improved slightly to 0.8472; early correction is delicate, with larger or later early bumps quickly hurting coupling.
