# microscope: summary

Chip `mmi_tree` (LNOI400, 1 x 8 MMI tree). I looked at every route waveguide along its full length. Scripts and
pictures are in `work/microscope/`.

## What I checked, and how much of the chip

| Check | Method | Coverage |
|---|---|---|
| Ridge width and position along each route | `walk.py`: `rv.cross_section` every 0.25 um, the cut kept normal to the measured centre line; ridge width, ridge centre jumps, slab width, ridge position in the slab | 15 of 15 routes from pin to pin, 34,255 cuts, 8,564 um of route (100 %) |
| Width inside the bends (exact) | `width_exact.py`: distance from each vertex of one ridge side to the other side | 17 of 17 curved ridge polygons |
| Bend radius | `radius_fit.py`: least-squares circle fit to each side of each arc (s-bends split at the inflection) | 17 of 17 curved polygons, 30 arcs |
| Joints | `joints.py`: the shared boundary length of every pair of touching ridge polygons; cuts 0.05 um each side of every device pin | 30 of 30 route-to-device joints, 22 of 22 piece-to-piece joints (plus 21 MMI-internal joints) |
| Hidden notches or bumps | `compare_bends.py`: symmetric difference and Hausdorff distance of each curved polygon against its mirrored sibling | 17 of 17 curved polygons on LN_RIDGE and LN_SLAB |
| Device cells at the joints | fingerprint of the chip EC and MMI against the PDK defaults (`edge_coupler()`, `mmi1x2_optimized1550()`) | 2 of 2 cell types: equal |
| Loss of each defect | local mode solver only: `rv.modes`, `rv.junction_loss`, my own straight-to-bend overlap (`bend_overlap.py`) and a short-section mode expansion with 80 local modes (`eme.py`) | every defect below |

## Results

All routes are 1.000 um (+-0.006 um vertex error in the arcs) on LN_RIDGE, on a centred 10 um LN_SLAB, and all joints
share their full 1.0 um cap, except at the places below. Every arc is circular with R = 80.0 um (sides 79.50/80.50,
residual < 1 nm), except route_out_1 (R = 100.0) and route_out_6 (R = 25.0).

The intent reviewer had posted the same ten items first, so I confirmed each with my own measurements and did not
post duplicates:

| My post | Confirms | Place | What I measured | Severity |
|---|---|---|---|---|
| microscope-1 | intent-2 | route_l1_1, x 657.05, y -81.65 and -174.0 | ridge-centre jumps +0.299 / -0.299 um; 0.90 dB per step, about 1.8 dB on EC#12-15 | high |
| microscope-2 | intent-3 | route_l2_2, x 1546.846-1556.846, y -127 | 40 cuts with no ridge; the 10 x 1 um piece is on LN_SLAB; more than 5 dB on EC#12-13 | high |
| microscope-8 | intent-1 | EC#13, y -187.5 | route_out_5 meets the moved coupler on axis (R = 80 s-bend, dy 58.85 um); the pitch is wrong, about 17 dB | high |
| microscope-3 | intent-4 | route_in, x 489.239-489.739, y 0 | 0.500 um ridge gap; mode expansion gives 0.2 to 1.4 dB on all 8 outputs | medium |
| microscope-6 | intent-5 | route_out_6 | R = 25.0 um circular 90 deg arcs; 0.30 dB radiation + 4 x 0.178 dB transitions = about 0.95 dB; +21.09 um path | medium (at the edge of high) |
| microscope-4 | intent-6 | route_l2_3, x 1332.954-1700.0, y -381 | 1467 cuts at 0.600 um; abrupt steps on axis; 0.06 dB and a group-delay skew equal to 6.6 um of path | medium |
| microscope-5 | intent-7 | route_l1_0, x 656.75, y 136.718-138.718 | 0.400 um x 2.0 um neck, on axis; 0.15 to 0.58 dB on EC#8-11 | medium |
| microscope-7 | intent-8 | route_out_1 s-bend | R = 100.0 um, walked length 2.27 um shorter than route_out_0 | low |
| microscope-9 | intent-9 | MMI#5 | at x +0.3 um; routes adjusted, joints on axis, path sums equal | none |
| microscope-10 | intent-10 | route_out_0, x 1903.109 and 2340 | 10 nm step (shared cap 0.99 um), 0.001 dB per joint | none |

I also agree with twins-12: the mirrored R = 80 bends differ only in vertex count, with a Hausdorff distance of 5 nm or
less against their siblings, so that is harmless.

I found nothing more on the route geometry. The slab has no gap or narrowing on any route, and the ridge is centred in
its slab everywhere, except on the shifted straight of route_l1_1.

## What I could not check

- I have no full-wave check of the losses (no cloud). The gap and neck numbers come from local mode overlaps and an
  80-mode expansion that leaves out reflection. The basis is not complete (about 87 % for the slab section), so I give a
  range, not one number.
- I did not check the inside of the device cells beyond their fingerprints against the PDK defaults, which are equal.
- I did not check process variation or sidewall roughness. Roughness can push the R = 25 bend of route_out_6 above 1 dB.
