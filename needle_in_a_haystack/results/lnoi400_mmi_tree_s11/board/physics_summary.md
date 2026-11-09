# Physics reviewer summary: mmi_tree (lnoi400, RWG1000, TE, 1550 nm)

## What I did

1. Built a sensitivity table for the RWG1000 rib with the local mode solver only (`rv.modes`, `rv.junction_loss`, and my own
   overlap / eigenmode scripts on `rv._solve`): side offset, width step, mode index vs width, bend radiation, straight/bend
   joint, slab-only section ("ridge on another layer"), double offset step with the TE0/TE1 beat, MMI output-arm coupling.
   Scripts: `work/physics/sens_table.py`, `two_step.py`, `gap.py`, `bend_trans.py`, `r25_coherent.py`,
   `mmi_arm_coupling.py`, `scan.py`, `overlap.py`. Raw numbers: `work/physics/sens_*.json`.
2. Read the board and put a number on every finding of the other reviewers (posts physics-1 to physics-9).
3. Searched for further defects with the table (scan.py): every route ridge piece outside devices (100 %) for width
   > 1.04 um (none), every pair of route pieces closer than 4 um (only the 7 MMI output pairs, 2.3 um, all alike),
   every ridge against the slab etch windows (no ridge on etched slab), device cells (one EC cell, one MMI cell).

Technology facts that matter for the ratings (from `tech().extrusion_specs`): the 0 to 0.2 um LN film is drawn
everywhere (empty mask); LN_SLAB (3/0) only protects the film inside SLAB_NEGATIVE (3/1) windows; the ridge (0 to 0.4 um)
is LN_RIDGE + LT_RIDGE_PERIODIC + LABELS (4/0) + ALIGN (31/0). So a ridge piece moved to LN_SLAB becomes a bare 200 nm slab,
and any polygon on LABELS or ALIGN near a route would act as LN waveguide (none on this chip).

## Sensitivity table (local mode solver, RWG1000 1.0 um ridge, TE0 n_eff 1.7915, n_g 2.190)

| Change | Value | Loss / effect |
|---|---|---|
| Side offset at a joint (per joint) | 0.025 / 0.05 / 0.1 / 0.2 / 0.3 / 0.5 / 1.0 um | 0.006 / 0.025 / 0.100 / 0.40 / 0.90 / 2.47 / 9.05 dB (Gaussian fit w0 = 0.47 um) |
| Two opposite offset steps, TE1 beat between them | 0.1 / 0.2 / 0.3 um | 0.10-0.30 / 0.40-1.23 / 0.88-2.85 dB (depends on beat phase) |
| Width step 1.0 -> w (per step) | 0.9 / 0.8 / 0.7 / 0.6 / 0.5 / 0.4 / 0.3 um | 0.002 / 0.006 / 0.014 / 0.030 / 0.067 / 0.167 / 0.433 dB |
| Width step 1.0 -> w (per step) | 1.2 / 1.5 / 2.0 / 3.0 um | 0.009 / 0.070 / 0.28 / 0.92 dB |
| TE0 n_eff / n_g vs width | 0.3 / 0.4 / 0.5 / 0.6 / 0.8 / 1.0 / 1.2 / 1.5 / 2.0 um | 1.687/2.036, 1.705/2.084, 1.724/2.123, 1.742/2.151, 1.771/2.180, 1.792/2.190, 1.806/2.192, 1.821/2.190, 1.836/2.184 |
| TE1 | 1.0 um | n_eff 1.660 (weakly guided above the slab 1.647); not guided below ~0.6 um |
| Bend radiation, TE0 (dB/cm) | R 80 / 60 / 50 / 40 / 30 / 25 / 20 / 15 / 10 um | 0.02 / 0.01 / ~0 / 0.7 / 10 / 38.4 / 187 / 669 / 2869 (+-1 dB/cm is noise) |
| Per 90-deg arc | R 30 / 25 / 20 / 15 / 10 um | 0.05 / 0.15 / 0.59 / 1.6 / 4.5 dB |
| Straight <-> bend joint | R 80 / 25 um | 0.013 (floor ~0.003) / 0.178 dB per joint |
| Slab-only section (ridge drawn on LN_SLAB or SLAB_NEGATIVE), length L | 0.5 / 1 / 2 / 5 / 10 um | lateral diffraction 0.07 / 0.26 / 0.78 / 2.47 / 4.59 dB, + vertical ridge->slab 0.30 dB per end (upper bound for short L) |
| rv.junction_loss(layer2='LN_SLAB') | per joint | 4.66 dB (overlap with a boxed slab mode; not the section loss) |
| Coupling between two 1.0 um ridges | gap 2.3 / 3.0 / 4.0 um | coupling length 8.1 mm / 59 mm / 1 m |
| Fibre (MFD 3 um) lateral offset | 0.5 / 1 / 3 um | 0.5 / 1.9 / 17.4 dB (MFD 3.5 um: 12.8 dB at 3 um) |

Rules of thumb for this PDK: a side offset becomes a defect (> 0.05 dB) at about 0.07 um; a width step at about
0.5 um wide or 1.5 um wide; bends are free down to R = 50 um and cost > 0.05 dB per quarter turn below R = 30 um; any
ridge gap longer than ~0.2 um is a defect.

## Findings (all confirmations with numbers; no new defects found)

| Id | Confirms | Finding | My number | Severity |
|---|---|---|---|---|
| physics-1 | intent-2 | 0.3 um double side step, route_l1_1 (x 657, y -81.65 / -174.0) | 0.9 to 2.8 dB (mean 1.8) on EC#12..15: the TE1 excited at step 1 is guided over 92.35 um and recouples at step 2; the beat phase (49 rad) varies chip to chip; ~150 nm spectral beat period | high |
| physics-2 | intent-5-update, disputes twins-5 | R=25 double bend in route_out_6 | ~1.27 dB: 0.30 radiation + 2 x 0.178 end joints + 0.61 dB middle (the 11.85 um straight is 1.002 TE0/TE1 beat lengths, the worst phase for an S-turn); above 1 dB, so high; + 21.09 um length | high |
| physics-3 | intent-3 | 10 um ridge on LN_SLAB in route_l2_2 | ~5.2 dB on EC#12/13 | high |
| physics-4 | intent-4 | 0.5 um ridge gap on the input | 0.1 to 0.7 dB on all 8 outputs; reflection ~-22 dB at worst | medium |
| physics-5 | intent-1 | EC#13 3 um off the 127 um grid | 13 to 17 dB at a fibre array | high |
| physics-6 | intent-6 | 0.6 um wide 367 um straight | 0.06 dB; group path -14.4 um (= 6.6 um of RWG1000), 2x phase sensitivity to width | medium |
| physics-7 | intent-7 | 0.4 x 2 um neck | 0.08 to 0.33 dB on EC#8..11 | medium |
| physics-8 | intent-8 | R=100 s-bend | no loss; -2.28 um length only | low |
| physics-9 | intent-9, intent-10 | MMI#5 +0.3 um; 10 nm step | 0 / 0.001 dB | none |

Checked and harmless (not posted as findings): the changed escape bends at MMI#7 (R=25) and MMI#4 (R=100) do not change
the MMI split; the integrated arm-to-arm coupling is < 0.001 rad for all variants (power exchange < 1e-6). TE1 excited
at the second step of intent-2 is radiated in the following R=80 bend, so it does not unbalance MMI#3.

## Excess loss per output (vs the intended layout; common input gap 0.1 to 0.7 dB on all outputs not included)

| Output | Defects on the path | Excess |
|---|---|---|
| EC#8, EC#9, EC#10, EC#11 | neck (intent-7); EC#9 also -2.28 um | 0.1 to 0.3 dB |
| EC#12 | double step (intent-2) + 10 um gap (intent-3) | 6.1 to 8.0 dB |
| EC#13 | as EC#12 + 3 um off the fibre array (intent-1) | 19 to 25 dB |
| EC#14 | double step + 0.6 um section + R=25 bends (+21.09 um) | 2.0 to 4.2 dB |
| EC#15 | double step + 0.6 um section | 1.0 to 2.9 dB |

The 1 x 8 splitter does not meet its function: the outputs spread by ~8 dB without the fibre-array loss of EC#13.

## What I could not check

- No FDTD or EME with reflections (cloud only): gap and neck numbers are brackets from mode expansions; facet reflections
  and Fabry-Perot ripple are only estimated.
- The edge-coupler facet mode was not solved; I used the intent's ~3 um MFD with a Gaussian.
- Sidewall-roughness loss (it raises the R=25 and the 0.6 um section numbers) and fabrication spread of the TE1 beat
  phases are not modelled; the MMI itself was not simulated (one cell, identical everywhere).
