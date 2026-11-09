# twins reviewer: summary (mmi_tree, lnoi400)

Job: find the things that must be identical, and the odd one out.

## Twin groups and how I compared them

| Group (from DESIGN_INTENT.md) | Members | How | Coverage |
|---|---|---|---|
| Devices against the PDK | 7 MMIs, 9 edge couplers | `rv.cell_shapes` + `rv.fingerprint` against a fresh `lx.mmi1x2_optimized1550()` / `lx.edge_coupler()` (XOR area) | 100 % of device cells: identical to the PDK defaults (0ec2bdb2a5ef, edca35fe1ccc) |
| Placement on a pitch | MMI x/y per stage, 8 output ECs | `rv.instances()` origins against the intent table | 100 % |
| Whole-chip mirror symmetry about y=0 | every shape | XOR of the flat union per layer with its mirror (`work/twins/s6.py`) | 100 % of LN_RIDGE, LN_SLAB, SLAB_NEGATIVE |
| Same-kind routes inside one half | 2 level-1, 4 level-2, 8 output routes | translate to the start pin, mirror, XOR + Hausdorff (`s7.py`); per-piece centre-line length and width from area and perimeter (`s3.py`) | 100 % of routes |
| Bend shapes | 4 level-1 bends | every vertex against the ideal arc (`s10.py`) | 100 % of 90-deg R=80 bends |
| Route-to-pin junctions | all 31 optical pins | cross-sections at -0.3, -0.02, +0.02, +0.3 um of each pin (`s9.py`) | 100 % of pins |
| Path lengths | 8 input-to-output paths | sum of route centre lines (devices identical, so they cancel) | 100 % |

Physics: local mode solves only (`rv.modes`, `rv.junction_loss`, a straight-to-bend overlap at R=25/80 in `s5.py`, and
a 40-mode eigenmode expansion of a slab-only section in `s11.py`).

## Results

Every outlier I found had already been posted by `intent`. I confirmed each one with independent twin evidence and
added numbers where they changed the picture. Route sums (reference path 2012.92 um of routes):

| Output | Path | Odd one out |
|---|---|---|
| EC#8 | 2012.92 | 10 nm step (harmless) |
| EC#9 | 2010.65 (-2.27) | R=100 s-bend |
| EC#10, EC#11 | 2012.92 | MMI#5 +0.3 um, absorbed by the routes |
| EC#12 | 2012.92 | |
| EC#13 | 2011.47 (-1.45) | coupler 3 um off pitch |
| EC#14 | 2034.00 (+21.08) | R=25 Manhattan route |
| EC#15 | 2012.92 | |

| My id | Confirms | Finding | Severity |
|---|---|---|---|
| twins-1 | intent-1 | EC#13 at y=-187.5, off the 127 um pitch (~17 dB at a fibre array) | high |
| twins-2 | intent-2 | route_l1_1 straight 0.30 um off its bends, two steps, ~1.8 dB on EC#12..15 | high |
| twins-3, twins-11 | intent-3 | route_l2_2: 10 um of ridge on LN_SLAB; eigenmode expansion 5.4 dB | high |
| twins-4 | intent-4 | route_in 0.5 um ridge gap (DRC + LVS flag it) | medium |
| twins-5 | intent-5 | route_out_6 R=25 bends: 0.30 dB radiation + ~0.66 dB from 4 transitions, ~0.9 dB; +21 um | medium (near 1 dB) |
| twins-6 | intent-6 | route_l2_3 straight 0.6 um: 0.06 dB, ~6.6 um group-delay skew | medium |
| twins-7 | intent-7 | route_l1_0 0.4 um x 2 um neck, up to 0.33 dB | medium |
| twins-8 | intent-8 | route_out_1 s-bend R=100: -2.27 um, no loss | low |
| twins-9 | intent-9 | MMI#5 x+0.3 um, routes compensate: harmless | none |
| twins-10 | intent-10 | route_out_0 10 nm offset: harmless | none |
| twins-12 | (new) | mirrored bends differ only in vertex count, vertices within 1 nm of the arc | none |

All other twins match: s-bends within 6 nm, slabs centred, all other pins on axis and 1.0 um wide, MMI and EC
cells equal to the PDK.

Path power after the defects (from the estimates above, excluding the fibre-array effect): EC#8..11 lose ~0.3 dB
(neck) + the common input gap; EC#12..13 ~1.8 dB + ~5.4 dB; EC#14 ~1.8 + 0.06 + ~0.9 dB; EC#15 ~1.8 + 0.06 dB.

## What I could not check

- No FDTD: the R=25 transition loss and the 0.5 um gap loss are mode-overlap or eigenmode estimates (+-50 %).
- A defect that is the same in every member of a group cannot be seen by a twin check. The device cells are
  covered by the PDK comparison. A route defect common to all members is not.
- No pin layers and no DRC deck in this PDK, so pins come from `detect_ports` only.
