# twins reviewer: summary (mzi_loopback, siepic_ebeam)

## What I checked and how

I grouped the things that the intent says must be the same, compared each group, and measured each outlier.
Scripts and pictures are in `work/twins/`.

| Group | Members | Compared | Coverage |
|---|---|---|---|
| Grating couplers | 6 (GC0 to GC5) | cell fingerprint vs the siepic_forge library cell, x, y pitch, angle, mirror, flat shapes in each bbox | 6/6 |
| Y-branches | 4 | library fingerprint, position relative to its GC, angle, pin positions | 4/4 |
| Crossing and terminators | 1 + 2 | library fingerprint, 4-fold symmetry of the crossing, terminator placement symmetry | 3/3 |
| Input routes GC to device | route_a_in, route_b_in, route_c_in | width, centre offset at both joints, length | 3/3 |
| Short arms | route_a_short, route_b_short | layers, number of parts, gaps, length | 2/2 |
| Long arms | route_a_long, route_b_long | segment by segment (same bend cells, leg lengths), dL of each MZI | 2/2 |
| Output routes device to GC | route_a_out, route_b_out, route_c_out | every polygon: width, bend radius (from area), continuity | 3/3 |
| Terminator routes | route_c_term_N, route_c_term_S | fingerprint (identical) | 2/2 |
| Bend cells | 3 bend cells + 1 S-bend | radius from bbox and area, mirror relation | all |
| Pins | all 24 optical pins | `rv.cross_section` on both sides of every pin | 24/24 |

Tools: `rv.instances`, `rv.cell_shapes`, `rv.fingerprint`, `rv.flat`, `rv.query`, `rv.cross_section`, `rv.extraction`,
`rv.lvs`, `rv.drc`, `rv.junction_loss`, `rv.modes` (local solves, including straight-to-bend overlap at R = 2 and 5 um,
`work/twins/t8.py`), `rv.render`, and the siepic_forge library cells for the device comparison. All the Si shapes on the
chip (441) are inside the 25 top-level references; there are no loose shapes other than the (99, 0) floor-plan box.

## Findings

| id | severity | finding |
|---|---|---|
| twins-1 | high | MZI A short arm: 5 um of the core on Si Slab (2/0, 90 nm) instead of Si (1/0), x 58.774 to 63.774, y 2.75. About 1 dB per joint, about 2 dB in all. Extraction counts the slab as connected, so LVS does not see it. |
| twins-2 | high | MZI B short arm: 0.5 um gap in the core at x 137.149 to 137.649, y 256.75. LVS sees it. Same as microscope-1. |
| twins-3 | high | route_c_in (GC4 to crossing) is 0.15 um off axis at both joints: 1.7 dB per joint, about 3.4 dB on the loopback. DRC flags it with SiEPIC-1a. Same as intent-2. |
| twins-4 | medium | route_a_in is 0.30 um wide for its full 32.6 um, with steps to 0.5 um at both ends: 0.05 dB per step, about 0.1 to 0.15 dB. DRC flags it with SiEPIC-1a. |
| twins-5 | high | route_a_out vertical leg has a 0.25 um wide, 2 um long neck at x 265, y 19.02 to 21.02: 0.86 dB per step, about 1.7 dB. |
| twins-6 | medium | route_b_out has two bends with R = 2.0 um (the rule is 5 um or more; routes A and C use 5 um): about 0.08 dB per bend, 0.13 dB more than R = 5. Same as intent-5. |
| twins-7 | medium | GC3 is at y = 383.0, not 381.0 (pitches 127, 127, 129, 125, 127.1): 0.3 to 0.6 dB fibre-array penalty on MZI B. Same as intent-3. |
| twins-8 | none | GC5 is 0.1 um off pitch, and an R = 5 um S-bend takes it up. Effect is less than 0.05 dB. Same as intent-4. |
| twins-9 | none | route_b_in is 5 nm off axis: 0.004 dB. The PDK DRC flags it (SiEPIC-1a, 21 nm Si_space notch), so fix it or waive it. |
| twins-10 | none | The crossing is at 90 deg, so the loopback uses the opt2/opt3 pair. LVS reports 4 mismatched nets, but the crossing is 4-fold symmetric (0.004 um2 difference), so the loopback still goes straight through and both terminators are in place. |
| twins-11 | none | MZI B dL = 60.34 to 60.40 um, inside 60.0 +-0.5 um. |
| twins-c1 | confirms intent-1 (high) | MZI A dL = 80.0 um (intent 100.0). The long-arm vertical legs are 34.264 um; they must be 44.26 um. |
| twins-c2..c6 | confirms | microscope-1, intent-2, intent-3, intent-4, intent-5 (each is the same defect as one of my posts). |

I re-posted twins-3, twins-4 and twins-9 with the same id after the DRC run, to set `drc_or_lvs_flags_it = True`.
The later post replaces the earlier one.

What each path carries:
- MZI A (GC0 to GC1): the 0.3 um input (twins-4), the Si Slab piece in the short arm (twins-1), dL 80 um instead of 100 um (intent-1), the 0.25 um neck on the output (twins-5).
- MZI B (GC2 to GC3): the cut short arm (twins-2), the R = 2 um bends (twins-6), GC3 off pitch (twins-7).
- Loopback (GC4 to GC5): the 0.15 um offset at both joints (twins-3).

## What is the same (checked, no defect)

- All four device cells (GC, Y-branch, crossing4, terminator) match the siepic_forge library cell exactly on every layer.
  Every instance is placed at angle 0 or 180 with no mirror, and all six GCs are on x = 0 and face +x.
- The two Y-branch pairs are at the same positions relative to their GCs (x = 40 and 200). Both MZIs use the same arm
  assignment (short arm on +2.75, long arm on -2.75).
- The R = 5 bend cells are exact mirrors of each other (zero symmetric difference). All R = 5 bends have the same area,
  and all straights are 0.500 um wide except the two outliers above.
- The terminator routes are identical (10.2 um), and the terminators are placed symmetrically.
- Every route cell is one connected polygon, except route_b_short (gap) and, on Si only, route_a_short (slab piece).

## What I could not check

- Losses are mode-overlap estimates with no reflection. The 0.5 um gap and the Si Slab section also make a Fabry-Perot
  etalon, which an FDTD run would quantify; I did not run one (no cloud).
- The fibre-array penalty uses a Gaussian model (MFD 10.4 um) of the GC field.
- I did not judge whether layer 2/0 is fabricated in the target EBeam run. If it is not, twins-1 is a 5 um gap and is worse.
