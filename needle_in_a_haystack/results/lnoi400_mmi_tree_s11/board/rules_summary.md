# rules reviewer: summary (mmi_tree, lnoi400)

## Standard checks and where they come from

- `rv.summary()`: `drc_deck: false`, `pin_layers: false`. The PDK has no DRC deck. `rv.drc()` is the adapter's basic check:
  LN_RIDGE width >= 0.25 um and space >= 1.0 um. It does not check bend radius, width changes, offsets, pitch or lengths.
- `rv.drc()`: 1 marker, `LN_RIDGE.space<1.0` at [489.239, -1.0, 489.739, 1.0]. Cause: a 0.500 um cut in the input ridge
  (route_in), with the slab continuous below. It is a real defect, not a false alarm (rules-1 / intent-4).
- `rv.lvs()` (pins found by `detect_ports`, nets from LN_RIDGE contact): 13 of 15 nets match. There are 2 open nets and
  no shorts:
  - EC#0.P0 to MMI#1.P0: the same 0.5 um cut (rules-1 / intent-4).
  - MMI#3.P2 to MMI#6.P0: a 10 um section of route_l2_2 drawn on LN_SLAB instead of LN_RIDGE. Basic DRC misses it because
    the gap is longer than the 1.0 um space rule (rules-2 / intent-3).

## Checks I wrote for the rules that DRC and LVS do not cover (scripts in work/rules/)

| Rule | Check | Coverage | Result |
|---|---|---|---|
| Route ridge is 1.0 um, no width changes | Morphological opening and erosion of every route ridge piece outside the device boxes (s7_width.py) | 39 of 39 route pieces (100 %) | 2 narrow regions: 0.6 um x 367 um in route_l2_3 (intent-6), 0.4 um x 2 um in route_l1_0 (intent-7). No wide regions (only polygon slivers of nm size on the arcs). |
| Only the route layers in routes | Ridge-on-slab check, slab-far-from-ridge check, slab width 10 um (s7, s16) | all LN_RIDGE and LN_SLAB route shapes | ridge always on the slab. Anomalies: the 1 x 10 um LN_SLAB filler in the route_l2_2 gap, and the asymmetric slab margin caused by the 0.3 um ridge offset. No other layers in the routes. |
| Bend radius >= 80 um | Curvature of the polygon edges with a circle fit over a window of vertices, per side (s8b_radius.py) | all 17 curved pieces | R=25 um on both bends of route_out_6 (intent-5). R=100 on route_out_1 (allowed, but it changes the length, intent-8). All others are 80 um. |
| Route meets the port on axis | Ridge cross-section 0.05/0.5/2 um outside all 30 device pins, plus a check for micro gaps at the pins (s14, s17) | 30 of 30 pins | EC#8.P0 is 10 nm off (harmless, intent-10). MMI#7.P0 meets a 0.6 um ridge (intent-6). There are no gaps at any port. Separately, the vertical straight of route_l1_1 is 0.3 um off the axis of both of its bends (intent-2). |
| 127 um output pitch on the facet | Instance origins of the 8 output edge couplers | 8 of 8 | EC#13 is at y=-187.5, not -190.5 (pitch 124/130) (intent-1). All facets are at x=2700 and the input facet is at x=0. |
| Equal path length +-0.5 um | Sum of centre-line lengths per path (area/width, with corrections for the neck and the gaps) | 8 of 8 paths | nominal 1873.10 um. EC#9 -2.28 (intent-8), EC#13 -1.49 (intent-1), EC#14 +21.09 (intent-5). EC#14 and EC#15 also have a group-delay skew of about 6.6 um equivalent from the 0.6 um section (intent-6). The other paths are within 0.01 um. |
| Device cells unchanged | Fingerprint of the MMI and edge-coupler cells against the PDK default PCells | 7 MMI + 9 EC (each is one shared cell) | identical to the PDK defaults |
| No stray shapes | Every route piece belongs to an extracted net | 39 of 39 pieces | none |

## Loss estimates (local only, no cloud)

- Lateral offset: `rv.junction_loss(offset=0.3)` gives 0.90 dB per step. The scaling is quadratic (0.1 um gives 0.10 dB).
- Width steps: 1.0 to 0.6 um gives 0.030 dB per step. 1.0 to 0.4 um gives 0.167 dB per step.
- Bends: R=25 gives 38.4 dB/cm (78.5 um of arc, 0.30 dB, transition losses not included). R=80 gives 0.023 dB/cm.
- Ridge gaps: I used a 2D x-z Helmholtz solve, TE, 400 nm to 200 nm LN, oxide cladding (s13b_gap2d.py), plus Gaussian
  lateral diffraction. A 0.5 um gap gives 0.3 to 0.7 dB. A 10 um gap gives about 6 dB.
- Pitch error: 3 um against a fibre MFD of about 3 um gives about 17 dB (Gaussian overlap).

## Findings (all confirm intent-N; I did not find a defect that the board did not already have)

| id | confirms | severity | what |
|---|---|---|---|
| rules-1 | intent-4 | medium | 0.5 um ridge gap on the common input (the DRC marker and the LVS open), 0.3-0.7 dB on all 8 outputs |
| rules-2 | intent-3 | high | 10 um of route_l2_2 is on LN_SLAB (LVS open), about 6 dB on EC#12 and EC#13 |
| rules-3 | intent-2 | high | two 0.3 um lateral steps in route_l1_1, about 1.8 dB on EC#12 to EC#15 |
| rules-4 | intent-1 | high | EC#13 is 3 um off the 127 um grid, about 17 dB |
| rules-5 | intent-5 | medium | R=25 um bends in route_out_6, 0.3 dB or more, +21.09 um length |
| rules-6 | intent-6 | medium | 0.6 um wide 367 um straight: about 0.06 dB, but the delay and phase matching of 2 outputs breaks |
| rules-7 | intent-7 | medium | 0.4 um x 2 um neck, 0.33 dB or less on EC#8 to EC#11 |
| rules-8 | intent-8 | low | R=100 s-bend makes the EC#9 path 2.28 um short (no loss) |
| rules-9 | intent-9 | none | MMI#5 is 0.3 um right of the table value; the lengths are balanced |
| rules-10 | intent-10 | none | 10 nm step at EC#8 |

## What I could not check

- I did not calculate the transition loss between a straight and a bend at R=25 um, or the reflection at the gaps. The
  gap losses come from a 2D model plus a Gaussian lateral estimate, not from a 3D solve (FDTD is cloud only).
- Extra scattering loss in the narrow 0.6 um and 0.4 um sections (it depends on the sidewall roughness).
- There is no foundry DRC deck, so there are no foundry rules for etch, slab or SLAB_NEGATIVE. The chip has no
  CHIP_CONTOUR or exclusion layer, so I could not check the dicing or facet position against a chip outline.
