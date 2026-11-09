# Physics reviewer summary: mzi_loopback (siepic_ebeam, TE 1550 nm)

My job was to put a number on each finding. I used only local Tidy3D mode solves (no cloud). The scripts are in `work/physics/`.

## Sensitivity table for this PDK (500 x 220 nm Si strip, oxide clad, TE0 at 1550 nm)

Reference mode: n_eff 2.440, n_g 4.181. Its 1/e^2 lateral intensity width is 0.67 um.

### Side offset at a butt joint (same 0.5 um strip, per joint)

| offset (um) | loss (dB) | note |
|---|---|---|
| 0.005 | 0.002 | |
| 0.025 | 0.048 | the 0.05 dB budget is reached at about 25 nm |
| 0.05 | 0.19 | |
| 0.10 | 0.76 | |
| 0.15 | 1.70 | a scalar-H overlap gives 2.8 dB, so 1.70 dB is the optimistic end |
| 0.25 | 4.55 | |

Method: single-mode mode matching with power-normalised E x H overlaps, including reflection (`mm.py`). It agrees with `rv.junction_loss` to 3 digits. The loss grows as offset^2: a joint that looks good can cost dB.

### Abrupt width step from 0.5 um (per joint)

| to width (um) | n_eff | loss (dB) | reflection |
|---|---|---|---|
| 0.60 | 2.561 | 0.008 | -47 dB |
| 0.45 | 2.348 | < 0.01 (solver noise) | -45 dB |
| 0.40 | 2.223 | < 0.02 (noise) | -43 dB |
| 0.35 | 2.051 | < 0.05 (noise) | -56 dB |
| 0.30 | 1.827 | 0.04-0.05 | -34 dB |
| 0.25 | 1.601 (n_g 3.06) | 0.86-0.94 | about -14 dB |

The loss jumps between 0.30 and 0.25 um because the mode is close to cut-off (n_eff 1.60 against oxide at 1.444). The E x H overlap on the tool's coarse port grid (22 nm) has about 1% noise, so values under about 0.05 dB are noise. A scalar E or H overlap overstates width-step losses by 5 to 10 times. That overlap is the wrong quantity for high-contrast guides, so I did not use it.

### Piece on another layer (Si 220 nm to Si Slab 90 nm, 0.5 um wide)

- Slab strip: n_eff 1.685, n_g 2.97.
- One joint: 0.95-0.97 dB, reflection -18.8 dB.
- Through a 5 um section: 1.5-2.0 dB (mode expansion).
- Phase: +15 rad over 5 um.

### Bend radius (0.5 um strip, 90 deg). The R=2 solve needed 4 modes; with 2 modes the solver returns a spurious PML mode (n_eff 2.72).

| R (um) | radiation (dB/90deg) | straight-to-bend joint (dB) | per 90deg bend (dB) |
|---|---|---|---|
| 2.0 | 0.0003 | 0.040 | 0.080 |
| 2.5 | ~0 | 0.025 | 0.050 |
| 3.0 | ~0 | 0.017 | 0.034 |
| 4.0 | ~0 | 0.0095 | 0.019 |
| 5.0 | ~0 | 0.006 | 0.012 |
| 10.0 | ~0 | 0.0016 | 0.003 |

The joint mismatch scales as 1/R^2. Radiation is negligible down to R = 2 um.

### Short sections between two 0.5 um strips

Method: my own local mode expansion, `eme_yee.py`. It uses 100 modes of a PEC box 4 x 2.8 um, Yee fields, and edges on grid lines. Raw values are shown, then values corrected by T(L)/T(0). The expansion is not complete (T(0) = 0.88-1.14), so each value is good to about +-0.5 dB.

| section | loss (dB) |
|---|---|
| 0.25 um x 2.0 um neck | 3.0 raw / 3.3 corrected. With no recapture of radiated light: 1.9 |
| 90 nm slab x 5.0 um | 2.0 raw / 1.5 corrected |
| 0.5 um oxide gap | 6.2 raw / 5.8 corrected, plus about 2 x 0.3 dB Fresnel. A Gaussian estimate gives 10 dB |
| 0.30 um x 32.6 um | not reliable at this level. I use 2 x 0.045 dB from the joints, plus 0.01-0.03 dB extra scattering |

### MZI response with one arm attenuated (ideal Y-branches, `mzi.py`)

| arm loss (dB) | peak loss (dB) | extinction (dB) |
|---|---|---|
| 0.5 | 0.25 | 31 |
| 1 | 0.49 | 25 |
| 2 | 0.94 | 19 |
| 3 | 1.4 | 15 |
| 6 | 2.5 | 9.6 |
| 7 | 2.8 | 8.3 |

FSR = lambda^2 / (n_g dL) with n_g = 4.181.

### Fibre offset (Gaussian, MFD 10.4 um)

| offset (um) | loss (dB) |
|---|---|
| 0.1 | 0.002 |
| 0.5 | 0.04 |
| 1 | 0.16 |
| 2 | 0.64 |

## What each finding costs (my numbers, and my confirmation of the severity)

| finding (first id; duplicates) | location | cost | severity |
|---|---|---|---|
| intent-2 / twins-3: route_c_in 0.15 um off axis at both ends | y=508.15, x 0..115.2 | 2 x 1.70 = 3.4 dB on the loopback (up to 5.6) | high (physics-c1) |
| microscope-1 / twins-2: 0.5 um gap in MZI B short arm | x 137.149..137.649, y 256.75 | 6-7 dB in the arm; MZI B peak -2.5 to -2.8 dB, ER 8-10 dB; -12 dB reflector | high (physics-c4) |
| twins-1: 5 um of MZI A short arm on Si Slab | x 58.774..63.774, y 2.75 | 1.5-2.0 dB in the arm (rules: 0.7-1.5); peak -0.7 to -0.9 dB, ER about 20 dB, +15 rad phase; a dead arm if 2/0 is not made | high (physics-c5) |
| twins-5: 0.25 um x 2 um neck in route_a_out | x 265, y 19.02..21.02 | 1.9-3.3 dB on GC0->GC1 | high (physics-c6) |
| intent-1: MZI A dL 79.94 um | route_a_long legs | FSR 7.19 nm against 5.75 nm (tolerance +-0.03 nm) | high (physics-c8) |
| twins-4: route_a_in 0.30 um wide | x 0..32.6, y 0 | 0.09-0.15 dB; reflection about -34 dB per joint, so no ripple (physics-d1 corrects rules-c5) | medium, low end (physics-c7) |
| twins-6 / intent-5: R=2 um bends in route_b_out | (260,254), (262,381) | 0.08 dB each, 0.16 total, +0.13 dB against R=5 | medium (physics-c2) |
| twins-7 / intent-3: GC3 at y=383 | GC3 | 0.32-0.64 dB on GC2->GC3 | medium (physics-c3) |
| twins-10: crossing at 90 deg | (120,508) | 0 dB (4-fold symmetric) | none (physics-c9) |
| twins-8 / intent-4: GC5 +0.1 um and its R=5 s-bend | (0..200, 635) | about 0.035 dB | none (physics-c9) |
| twins-9: route_b_in 5 nm offset | y=254.005 | 0.004 dB (DRC notch only) | none (physics-c9) |
| twins-11: MZI B dL 60.34 | | 9.52 nm against 9.58 nm FSR; 60.67 um group-equivalent with the gap | none |

Path totals at the fringe peak (excess over the intended design):

| path | excess loss | other effect |
|---|---|---|
| GC0->GC1 (MZI A) | about 2.8-4.4 dB | wrong FSR |
| GC2->GC3 (MZI B) | about 3.0-3.6 dB | ER about 9 dB |
| GC4->GC5 (loopback) | about 3.4 dB | |

The loopback is the reference used to normalise both MZIs, so its error goes directly into both normalised spectra.

## What I checked and how

- I scanned all 24 optical pins with cuts 0.05 and 0.3 um on each side of each pin (`pinscan.py`, 100% of the pins). No offset or width step other than those already listed.
- I looked for disconnected Si islands and stray shapes (`islands.py`). There are 13 route groups, all attached to pins. Layer (99,0) is one chip-sized box. The black-box layer holds only text inside the grating couplers.
- I did not walk the full centre-line of the routes myself. The walkers of microscope and rules cover all of it, and I used their geometry.

## What I could not check

- No FDTD (cloud), so these numbers are not checked: the gap and short-section values (+-0.5 dB), the grating-coupler response with offset (the Gaussian fibre model is about +-30%), and the reflections in the gap and slab sections.
- I do not know if layer 2/0 (Si Slab) is fabricated in this EBeam run. If it is not, the twins-1 piece is a 5 um gap (> 30 dB, dead arm).
- Sidewall-scattering numbers are estimates, not modelled.
