# Intent review: mmi_tree (lnoi400, 1 x 8 MMI tree)

Reviewer: `intent`. Job: check that the layout does what `chip/DESIGN_INTENT.md` and `chip/intent_nets.json` say.
Scripts and pictures: `work/intent/` (`centerline.py`, `radius_fit.py`, `path_lengths.py`, `gap_eme.py`, `*.png`).

## How

- `rv.instances()`: every device position, angle, mirror (all 16 devices, all 15 route cells; 100 %).
- `rv.extraction()`, `rv.lvs()`, `rv.optical_net_geometry()`: connectivity against `intent_nets.json` (all 15 nets).
- `rv.cell_shapes()` per route cell: every LN_RIDGE / LN_SLAB piece of every route (100 % of the routing):
  width of every straight, centre-line start and end of every piece (junction offsets), bend radius by circle fit to
  both ridge edges (`radius_fit.py`), length by area / width (exact for constant width) or long side for rectangles.
- `rv.cross_section()` at each suspect point.
- `path_lengths.py`: total input-facet-to-output-facet length for all 8 paths (EC 360 um x 2, MMI 76.75 um x 3).
- Device cells compared with the PDK defaults (`luxtelligence_lnoi400_forge` `mmi1x2_optimized1550()`,
  `edge_coupler()`): XOR 0 on every layer; all 7 MMIs and 9 edge couplers are one cell each, so all copies are identical.
- XOR of every s-bend / bend against its sibling (mirrored where needed): identical to < 0.03 um^2.
- Local mode solves: `rv.modes` (w 1.0 / 0.6 / 0.4, R 25 / 80), `rv.junction_loss`, and an eigenmode-expansion
  estimate of the ridge gaps (`gap_eme.py`, 80 modes of the 10 um wide slab strip).

## Every checkable statement and its measured value

| # | Intent statement | Measured | Verdict |
|---|---|---|---|
| 1 | Input EC facet at x = 0, y = 0 | EC#0 origin (0, 0), angle 0, bbox x 0..360 | OK |
| 2 | MMI 0 input x = 500, y = 0 | MMI#1 input pin (500.0, 0.0) | OK |
| 3 | MMI 1, 2 input x = 1100, y = +254 / -254 | MMI#2 (1100, 254), MMI#3 (1100, -254) | OK |
| 4 | MMI 3..6 input x = 1700, y = +381, +127, -127, -381 | MMI#4 (1700, 381), **MMI#5 (1700.3, 127)**, MMI#6 (1700, -127), MMI#7 (1700, -381) | MMI#5 0.3 um off in x, harmless (intent-9) |
| 5 | 8 output ECs at x = 2700, y = +444.5..-444.5, 127 um pitch | y = 444.5, 317.5, 190.5, 63.5, -63.5, **-187.5**, -317.5, -444.5; pitches 127 x4, **124.0, 130.0**, 127 | **EC#13 3.0 um off pitch** (intent-1, high) |
| 6 | Connectivity = intent_nets.json (15 nets) | 13 match; **N0 (EC#0-MMI#1.P0) open, N14 (MMI#3.P2-MMI#6.P0) open**; no shorts, no extra nets | 2 opens (intent-4, intent-3) |
| 7 | Order of the outputs (tree, no crossings) | EC#8..EC#15 top to bottom fed by MMI#4.P2, #4.P1, #5.P2, #5.P1, #6.P2, #6.P1, #7.P2, #7.P1, as in the intent nets | OK |
| 8 | Every route is the 1.0 um ridge, no width changes, no tapers | all pieces 1.0 um except **route_l1_0: 0.4 um x 2 um neck** at (656.75, 136.72..138.72) and **route_l2_3: 0.6 um x 367.05 um straight** at y = -381; slab 10 um everywhere; no tapers | 2 width changes (intent-7, intent-6) |
| 9 | Every bend radius >= 80 um | 90-deg bends of route_l1_*: R = 80.0; s-bends: R = 80.0 (route_l2_*, route_out_0/2/3/4/5/7), R = 100.0 (route_out_1); **route_out_6: two 90-deg bends R = 25.0** | route_out_6 violates (intent-5) |
| 10 | Every route meets its port on axis, end to end | all route ends on their pin within 0.001 um; inside routes: **route_l1_1 straight 0.30 um sideways at both bends**, **route_in ridge gap 0.5 um**, **route_l2_2 ridge gap 10 um**, route_out_0 straight 0.01 um high | intent-2 (high), intent-4, intent-3 (high), intent-10 (none) |
| 11 | 8 paths equal length within +-0.5 um | totals 2963.353 (EC#8, #10, #11), 2963.349 (#12), 2963.348 (#15); **EC#9 -2.280, EC#13 -1.486, EC#14 +21.090** | 3 paths out (intent-8, intent-1, intent-5) |
| 12 | Unplanned loss <= 0.05 dB per path | see the per-channel budget below | violated on all 8 paths |
| 13 | Route cross-section RWG1000 (1.0 um ridge on LN_RIDGE, 10 um slab) | spec path_profiles (1.0 on 2/0, 10.0 on 3/0); ridge always over slab | OK |
| 14 | Devices are the PDK cells | MMI and EC XOR = 0 against the PDK defaults | OK |

Path-length notes: lengths that read short in `optical_net_geometry` for N11 (705.757) and N14 (436.714) are
area / width artefacts of the 0.4 um neck and the 0.6 um straight; the true centre-line lengths are 706.957 and
583.532 um, matched. The 0.3 um shift of MMI#5 is compensated (route_l2_1 +0.3, route_out_2/3 -0.3).

## Findings

| id | title | severity |
|---|---|---|
| intent-1 | EC#13 at y = -187.5, 3.0 um off the 127 um pitch (route_out_5 re-drawn to follow it) | high (~17 dB on that channel with a fibre array) |
| intent-2 | route_l1_1: vertical straight 0.3 um sideways from both R = 80 bends | high (~0.9 dB per step, ~1.8 dB on EC#12..#15) |
| intent-3 | route_l2_2: 10 um gap in the ridge at x 1546.85..1556.85, y = -127 (LVS open) | high (EME 4.7 to 5.3 dB on EC#12, #13) |
| intent-4 | route_in: 0.5 um gap in the ridge at x 489.24..489.74 (LVS open, common input) | medium (EME 0.08 dB normalised, <= 0.6 dB raw; on all 8 paths) |
| intent-5 (+ intent-5-update) | route_out_6: Manhattan route, two R = 25 um bends, +21.09 um length | posted medium, raised to high in intent-5-update: 0.30 dB radiation + 4 x 0.18 dB bend/straight mismatch = ~1.0 dB on EC#14 |
| intent-6 | route_l2_3: 367 um straight 0.6 um wide | medium (0.06 dB + 74 rad phase / 14.4 um group path on EC#14, #15) |
| intent-7 | route_l1_0: 0.4 um x 2 um neck | medium (~0.2 to 0.35 dB on EC#8..#11) |
| intent-8 | route_out_1: R = 100 s-bend, path to EC#9 2.28 um short | low (no loss; phase/delay matching only) |
| intent-9 | MMI#5 at x = 1700.3 instead of 1700.0, lengths compensated | none |
| intent-10 | route_out_0 straight 10 nm high | none (0.002 dB) |

## Extra loss per output channel (estimates, dB, on top of the planned tree)

| Output | Defects on the path | Extra loss |
|---|---|---|
| EC#8, #9, #10, #11 | route_in gap, 0.4 um neck | ~0.3 to 0.9 |
| EC#12 | route_in gap, l1_1 offsets, l2_2 gap | ~7 |
| EC#13 | as EC#12 plus 3 um fibre-array offset | ~24 (dead) |
| EC#14 | route_in gap, l1_1 offsets, 0.6 um straight, R = 25 bends | ~2.9 to 3.5 |
| EC#15 | route_in gap, l1_1 offsets, 0.6 um straight | ~1.9 to 2.5 |

The chip does not do its function: the 1 x 8 split is far from uniform (two channels 7 dB and ~24 dB down, the lower
half ~2 dB down) and three paths break the length-matching rule.

## Gap EME estimate (`gap_eme.py`)

RWG1000 ridge -> L um of the bare 10 um x 200 nm slab strip -> ridge, 80 local slab-strip modes, no reflection.
T(0) = 0.886 instead of 1 (the solved modes do not span the field completely), so raw and normalised values bracket
the answer: L = 0.5 um: 0.60 dB raw / 0.08 dB normalised; L = 10 um: 5.26 dB raw / 4.73 dB normalised.

## What I could not check

- Reflections at the gaps and width steps (no FDTD; overlap / EME estimates only).
- Coherent effects between the two R = 25 bends (the 11.85 um straight); bend/straight mismatch is a mode-overlap estimate (`bend_transition.py`).
- The planned performance of the MMIs and edge couplers (cells are the PDK defaults; their own loss is planned).
- Fibre-to-chip numbers use a Gaussian with 3 um MFD from the intent, not the real edge-coupler mode.

## Board cross-check (read at the end)

- twins-1..10 and rules-1..10 confirm intent-1..10 one for one, with independent measurements (mirror XOR, curvature fits,
  port cross-sections, path sums). No reviewer disputed any intent finding, and no other reviewer posted a defect that
  is not already on this list. microscope and physics had not posted when I finished.
- Severity differences: intent-5 (route_out_6) is rated medium by twins-5 / rules-5 and high by my intent-5-update
  (~1.0 dB with the bend/straight mismatch, 0.9 dB if the R = 80 floor is subtracted: it sits on the 1 dB line).
- My confirmations: intent-c1 (rules-1, input gap: EME bracket 0.08 to 0.6 dB, medium), intent-c2 (rules-2, 10 um gap:
  EME 4.7 to 5.3 dB, high), intent-c3 (twins-5, same 0.178 dB per R = 25 transition).
