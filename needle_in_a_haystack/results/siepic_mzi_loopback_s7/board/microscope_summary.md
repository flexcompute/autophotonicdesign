# Microscope review: mzi_loopback (siepic_ebeam)

Reviewer: microscope. Job: look at every waveguide along its full length: width, layer, joints, bends.
Scripts and pictures: `work/microscope/`.

## What I checked, and how

| Check | Method | Coverage |
|---|---|---|
| Width and layer along every route | `walk.py`: I start at a pin, take a step of 50 nm, cut across the core at three angles, keep the angle with the smallest width, recentre on the core and record the width on Si and on Si Slab. I stop at the next pin. `analyse.py` lists the runs where the width differs by more than 4 nm or where Si Slab is present, and then by more than 0.5 nm on straights. | All 12 extracted optical nets, about 2,219 um of centre line in total, 100 % of the routes. The cut-off arm of MZI B was walked from both ends (N8 and N10). |
| Gaps and necks | Gap search in the walker (look ahead 10 um). Union of each route cell (number of parts). Erosion by 0.245 um (finds any neck narrower than 0.49 um). | 12 of 12 route cells |
| Joints between a route and a device port | `joints.py`: cuts 30 nm inside the device and 30 nm inside the route at each of the 24 pins: width, centre, layer. Union inside a 0.4 um box at each pin (finds hairline gaps). | 24 of 24 pins |
| Joints between route pieces | Side jumps in the walker (recentring step larger than 3 nm, then 0.5 nm on straights). Edge tilt of all 37 rectangular route pieces. | All pieces |
| Bends | `bends.py`: a circle fit to both edges of each bend polygon, and the vertex distance from the corner centre. | 15 of 15 bends and the s-bend |
| Bend and junction physics | Local Tidy3D mode solves (`physics.py`, `bendloss.py`): junction overlaps for 0.3 um, 0.25 um, Si Slab and side offsets; straight-to-bend overlap at R = 2 um and R = 5 um. `gap_loss.py`: angular-spectrum estimate for the 0.5 um oxide gap. | All anomalies |
| Device cells | Each device cell compared with the `siepic_forge` PDK cell (symmetric difference per layer = 0). | 4 of 4 cell types |
| Spacing between nets, stray Si | Minimum distance between the route groups; Si outside devices and nets. | Whole chip |

## What I found (my measurements; most were also posted by twins and intent)

| Id | Location | Measurement | Severity |
|---|---|---|---|
| microscope-1 (= twins-2), c1 | MZI B short arm, x 137.149..137.649, y 256.75 | 0.500 um gap with no Si and no slab. My angular-spectrum estimate is about 7 dB (4.5 dB for a 0.25 um gap), so I do not agree with the 3 dB from the Gaussian model. MZI B does not work. | high |
| c2 (twins-1) | MZI A short arm, x 58.774..63.774 | The core is drawn on Si Slab (90 nm thick) for 5.000 um. The loss is 0.97 dB per face, about 1.9 dB in total. | high |
| c3 (intent-1) | MZI A | The walked arm lengths are 225.15 and 145.20 um, so dL = 79.95 um (intent: 100). All arm bends are R = 5.000 um, so the cause is the vertical legs, which are 34.26 um and not 44.29 um. | high |
| c4 (intent-2, twins-3) | route_c_in, GC4 and crossing opt2 | The centre is at y = 508.150 at both ends. The loss is 1.70 dB per joint (checked independently), about 3.4 dB on the loopback. | high |
| c5 (twins-5) | route_a_out, x = 265, y 19.02..21.02 | A neck 0.250 um wide and 2.00 um long, centred on the axis. The loss is about 1.7 dB. | high |
| c6 (twins-4) | route_a_in | 0.300 um wide over all 32.6 um, with abrupt steps at both ends. The loss is about 0.10 to 0.15 dB. | medium |
| c7 (intent-5, twins-6) | route_b_out bends | R = 2.000 um (edges 1.750 and 2.250 um, 0.5 nm). The loss is 0.079 dB per bend, against 0.012 dB at R = 5. | medium |
| c8 (twins-9) | route_b_in | 5.0 nm off the axis. 0.004 dB. | none |
| c9 (twins-8, intent-4) | route_c_out s-bend | R = 5 um, 0.1 um offset, on the axis at GC5. Less than 0.04 dB. | none |

The rest of the routes are clean:
- All other widths are 0.500 um to within 0.5 nm on straights. In bends the width is within 5 nm, which is the polygon vertex error.
- All straights are on the axis grid (edge tilt 0).
- The other 22 pin joints have 0.0 nm offset. The other 13 bends are R = 4.9996 um (circle-fit residual 0.5 nm).
- No other gaps or necks. No stray Si. The closest spacing between nets is 5.0 um.
- The device cells are identical to the PDK cells.

## Notes and limits

- The tool `rv.modes(bend_radius=2)` gives a spurious PML mode as mode 0 (n_eff 2.72, k 0.19). Use the low-k TE mode (n_eff 2.449).
- Loss values are mode-overlap estimates without reflection, except for the gap, where I added Fresnel reflection. I did no FDTD (no cloud).
- I did not look inside the device cells; I compared them with the PDK only. I did not run the KLayout DRC deck (it is outside the sandbox).
- GC3 pitch (intent-3, twins-7) and the 90 deg crossing (twins-10): my routes meet GC3 at y = 383.000 on the axis, and the crossing cell is identical to the PDK cell. I agree with those findings but did not post them again.
