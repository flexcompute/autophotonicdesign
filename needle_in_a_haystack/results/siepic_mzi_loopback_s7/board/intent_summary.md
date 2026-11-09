# Intent review: mzi_loopback (siepic_ebeam), reviewer `intent`

## What I checked and how

I listed every statement in `chip/DESIGN_INTENT.md` and `chip/intent_nets.json` that a number can check, then measured
each one in the layout:

- Connections and path order: `rv.extraction()`, `rv.lvs()`, `rv.pin_xy`. All 12 intent nets, all 13 devices (100 %).
- Device positions, angles and pitch: `rv.instances()`, FbrTgt shapes. All 6 GCs, 4 Y-branches, crossing, 2 terminators.
- Route width and layer: `rv.cell_shapes` of all 12 route cells (every polygon), `rv.cross_section` cuts on both sides of
  every route/device joint (31 cuts, `work/intent/junction_xs.py`). 100 % of route polygons.
- Bend radius: centre-line extraction of every bend and s-bend polygon (`work/intent/bends2.py`). All 17 bends.
- Path lengths and dL: straights from the instance tree plus bend centre-line lengths (pi/2 x R); cross-checked with
  `rv.optical_net_geometry()` (area / width).
- Devices against the PDK: Si geometry of the 4 device cells against `siepic_forge.component()`: symmetric difference
  0 for all four (`work/intent/device_vs_pdk.py`). No stray Si: 315 Si parts = 6 x 52 GC parts + 3 circuit networks.
  No overlapping Si shapes.
- Loss of each defect: `rv.junction_loss` / `rv.modes` (local Tidy3D), a 1-D effective-index cross-check of the offset
  loss (`work/intent/check_offset.py`), a local straight-to-bend overlap at R = 2 and 5 um
  (`work/intent/bend_overlap2.py`), a Gaussian fibre-offset estimate (MFD 10.4 um).
- PDK DRC deck (`rv.drc()`): SiEPIC-1a x 6, Si_space x 2.

## Each statement and its measured value

| # | Intent statement | Measured | Verdict | Finding |
|---|---|---|---|---|
| 1 | Si 1/0, 500 nm strip on every route | route_a_short: 5.0 um on Si Slab (x 58.774..63.774, y 2.75) | FAIL, high | twins-1 (confirmed intent-c1) |
| 2 | No width change: route_a_in | 0.300 um over all 32.6 um, steps to 0.53/0.50 at both ends | FAIL, medium (~0.1 dB) | twins-4 (intent-c3) |
| 3 | No width change: route_a_out | 0.250 um neck, 2.0 um long at x=265, y 19.02..21.02 | FAIL, high (~1-1.7 dB) | twins-5 (intent-c4) |
| 4 | All other routes 0.500 um | 0.500 um (bends 0.495-0.505 from polygon facets) | PASS | |
| 5 | Bend radius >= 5 um | route_b_out: 2 bends R = 2.0 um (arc 3.140 um); all other 15 bends R = 5.0 (arc 7.852); s-bend R = 5.0 | FAIL, medium (~0.16 dB) | intent-5 = twins-6 (intent-c5) |
| 6 | Route on axis at GC4 and crossing opt2 | route_c_in centre y = 508.150, pins at 508.000 (both ends) | FAIL, high (~3.0-3.4 dB) | intent-2 (= twins-3; DRC SiEPIC-1a flags it, intent-c8) |
| 7 | Route on axis at GC2 / Y#12 | route_b_in centre 254.005 (5 nm) | harmless (0.004 dB; DRC notch) | twins-9 (intent-c6) |
| 8 | Routes meet ports end to end: MZI B short arm | 0.500 um gap at x 137.149..137.649, y 256.75; nets N8/N10 open | FAIL, high (dead arm) | microscope-1 / twins-2 (intent-c2) |
| 9 | All other joints on axis | 0.000 offset at all other 22 joints | PASS | |
| 10 | GC0..GC5 at y = 0, 127, 254, 381, 508, 635 | 0, 127.0, 254.0, **383.0**, 508.0, **635.1** | GC3 FAIL medium; GC5 harmless | intent-3 (= twins-7), intent-4 (= twins-8) |
| 11 | GCs on one column, facing +x | all x = 0, angle 0, not mirrored | PASS | |
| 12 | MZI A: GC0 -> Y -> 2 arms -> Y -> GC1 | N4, N5, N11, N12 match intent | PASS | |
| 13 | MZI B: GC2 -> Y -> 2 arms -> Y -> GC3 | N6, N7, N9 match; N8 open (row 8) | FAIL | microscope-1 |
| 14 | Loopback GC4 -> crossing straight through -> GC5, other arms terminated | straight through (W -> E), crossing at 90 deg so pins opt2/opt3 instead of opt1/opt4; crossing Si is 4-fold symmetric (symdiff 0.0044 um^2) | harmless; LVS mismatch on 4 nets | twins-10 (intent-c7) |
| 15 | MZI A dL = 100.0 +-0.5 um | long 225.144, short 145.200 -> **79.94 um** (-20.06) | FAIL, high (FSR 7.19 nm vs 5.75 nm) | **intent-1** (confirmed twins-c1) |
| 16 | MZI B dL = 60.0 +-0.5 um | long 205.542, short 145.200 -> 60.34 um | PASS | twins-11 (intent-c9) |
| 17 | Devices are PDK cells | GC, Y, crossing, terminator Si identical to siepic_forge | PASS | |
| 18 | "Passed DRC and LVS" | LVS: 5 design-only nets (crossing x4 pin names, MZI B short arm). DRC: SiEPIC-1a x 6 (both ends of route_a_in, route_b_in, route_c_in), Si_space x 2 (GC2, GC4 joint notches) | no longer true | |

## What this does to each path

- MZI A (GC0 -> GC1): wrong dL (FSR +25 %), a 5 um slab section in the short arm (~1.9 dB, arm imbalance, extinction
  limited), a 0.25 um neck on the output (~1-1.7 dB), a 0.30 um input route (~0.1 dB). Does not meet its spec.
- MZI B (GC2 -> GC3): short arm open (no interference), GC3 2 um off pitch (0.3-0.6 dB), two R = 2 um bends (~0.16 dB).
  Does not do its function.
- Loopback (GC4 -> GC5): 0.15 um offset at both ends of route_c_in, ~3 dB. The GC reference is wrong by this amount.

## My posts

intent-1 (high, MZI A dL 79.94 um), intent-2 (high, route_c_in 0.15 um off axis), intent-3 (medium, GC3 at y = 383),
intent-4 (none, GC5 at 635.1), intent-5 (medium, R = 2 um bends; duplicate of twins-6, posted before I saw it).
Confirmations: intent-c1 (twins-1), c2 (microscope-1), c3 (twins-4), c4 (twins-5), c5 (twins-6), c6 (twins-9),
c7 (twins-10), c8 (twins-3, with the correction that the PDK DRC flags intent-2), c9 (twins-11). No disputes.

## What I could not check

- Loss numbers are mode-overlap estimates (no reflection, no FDTD): the 2 um neck and the 5 um slab section are short,
  so their real loss may differ from two-joint sums. Whether Si Slab (2/0) is fabricated in an EBeam run decides if the
  slab section is a lossy rib or an open gap.
- The fibre-offset loss assumes Gaussian modes of MFD 10.4 um; the real GC mode is not exactly Gaussian.
- Fringe phase of MZI A with the slab section (its n_eff changes the arm phase) was not computed.
