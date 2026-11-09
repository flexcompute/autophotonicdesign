# rules reviewer: summary (mzi_loopback, siepic_ebeam)

## What I checked and how

| Check | Tool | Coverage |
|---|---|---|
| PDK DRC | `rv.drc()`: the SiEPIC EBeam KLayout deck (`SiEPIC_EBeam_DRC`, batch copy). Rules in it: device overlap, boundary, Si/SiN/M1/M2/MLOpen width and space, M2-M1 overlap, SiEPIC-1a (PinRec must enclose one waveguide material). No bend-radius, no length, no layer-in-route, no gap check away from pins. | whole chip |
| LVS | `rv.lvs()` against `chip/intent_nets.json` (extraction connects Si and Si Slab) | all 13 devices, 24 pins |
| Each DRC marker and LVS mismatch traced to a shape | `rv.query`, `rv.cross_section`, `rv.junction_loss` | 8/8 markers, 5/5 mismatched nets |
| Only Si in routes | every route piece (device boxes removed) by layer | 100% of route shapes |
| Constant 0.5 um width | morphological opening (r = 0.248 um) and erosion (r = 0.252 um) of every route piece; end cross-sections at every pin | 100% of routes |
| Bend radius >= 5 um | centre-line length of every bend / s-bend cell (area / 0.5) | all 16 bend instances, 1 s-bend |
| Route ends on the pin axis | `rv.cross_section` 0.3 um outside every pin | 24/24 pins |
| GC column, pitch, orientation | `rv.find('ebeam_gc_te1550')` | 6/6 GCs |
| MZI dL | centre-line by area for every arm | both MZIs |
| Device cells vs the PDK library | XOR of each cell against `siepic_forge.component(name)`, every layer | GC, Y-branch, crossing, terminator: XOR 0 |
| Crossing symmetry | Si XOR after a 90 deg rotation | 0.0049 of 16.46 um2 |
| Stray shapes, overlaps, close approaches, 1 nm grid | union/overlap of all 441 Si shapes; route components within 2 um; vertex snapping | whole chip |
| Loss numbers | local Tidy3D mode solves only: `rv.junction_loss`, bend modes with PML (`work/rules/bends.py`), a local mode-expansion for short sections (`work/rules/mini_eme.py`) | n/a |

Scripts and outputs: `work/rules/` (`routes.py`, `lengths.py`, `rulecheck.py`, `bends.py`, `mini_eme.py`, `junctions.json`, `bends.json`, `rulecheck.json`).

## Standard checks: every flag and its cause

DRC is not clean: 6 x SiEPIC-1a, 2 x Si_space.

| Marker | Cause | Finding |
|---|---|---|
| SiEPIC-1a (0, 0) and (32.6, 0) | route_a_in is 0.30 um wide inside 0.5 um pins | twins-4 / rules-c5 |
| SiEPIC-1a (0, 254), (32.6, 254); Si_space (-0.067..0, 254.25..254.271) | route_b_in 5 nm off axis (step notch) | twins-9 / rules-c10 |
| SiEPIC-1a (0, 508), (115.2, 508); Si_space (-0.069..0, 508.25..508.322) | route_c_in 150 nm off axis (step notch) | intent-2 / rules-c4 |

LVS: 7 of 12 intended nets match.
- N8 (Y#12.opt2 - Y#13.opt3) is split into two one-pin nets: the 0.5 um gap in route_b_short (microscope-1 / rules-c2). `dangling` is empty, so read `design_only`.
- N0-N3 (crossing) differ by pin names only: the crossing is placed at 90 deg; the cell is 4-fold symmetric and the loopback still runs straight through (twins-10 / rules-c11). False alarm for the light.

## What DRC and LVS do not see (found by the rule checks)

| Rule | Result |
|---|---|
| Only Si in routes | 1 violation: 5.0 um of MZI A short arm on Si Slab (twins-1 / rules-c1) |
| No width change | 2 violations: route_a_in 0.30 um (DRC sees only its ends), 2 um neck of 0.25 um in route_a_out (twins-5 / rules-c6). Bend polygons are within a few nm of 0.5 um (arc discretisation, harmless). |
| Bend radius >= 5 um | 2 violations: R = 2.0 um bends in route_b_out (twins-6 / rules-c7). The s-bend in route_c_out is R = 5.0. |
| On axis | route_c_in +0.15 um, route_b_in +0.005 um; all other 20 pins 0.000 |
| GC column / pitch | x = 0 and angle 0 for all six; GC3 +2.0 um (twins-7 / rules-c8), GC5 +0.1 um (harmless, rules-c9) |
| MZI A dL | 80.00 um, intent 100.0 +-0.5: both vertical legs of route_a_long 10 um short (intent-1 / rules-c3) |
| MZI B dL | 60.40 um, in tolerance (rules-c12) |
| Devices | identical to the PDK library; no overlapping or stray Si; all vertices on the 1 nm grid |

## Findings (my ids; all confirm a first post by another reviewer)

| id | confirms | defect | severity |
|---|---|---|---|
| rules-c2 | microscope-1 / twins-2 | 0.5 um gap in MZI B short arm (~5-10 dB on that arm) | high |
| rules-c1 | twins-1 | 5 um of MZI A short arm on Si Slab (~1-2 dB arm loss; layer may not exist on a standard run) | high |
| rules-c3 | intent-1 | MZI A dL = 80.0 um instead of 100.0 (FSR 7.2 nm vs 5.75 nm) | high |
| rules-c4 | intent-2 / twins-3 | route_c_in 0.15 um off axis: 3.4 dB on the loopback | high |
| rules-c6 | twins-5 | 0.25 um x 2 um neck in route_a_out: ~1.7-2.6 dB | high |
| rules-c5 | twins-4 | route_a_in 0.30 um wide: ~0.1-0.3 dB plus ripple | medium |
| rules-c8 | twins-7 / intent-3 | GC3 2 um off pitch: ~0.3-0.6 dB | medium |
| rules-c7 | twins-6 / intent-5 | two R = 2 um bends: +0.13 dB | medium |
| rules-c10 | twins-9 | route_b_in 5 nm off axis: 0.004 dB, but 3 DRC markers (fix or waive) | low |
| rules-c9 | twins-8 / intent-4 | GC5 +0.1 um and its R = 5 s-bend: ~0.04 dB | none |
| rules-c11 | twins-10 | crossing at 90 deg: LVS pin names only | none |
| rules-c12 | twins-11 | MZI B dL 60.40 um | none |

## What I could not check

- Loss numbers for the gap, the slab section and the neck are local estimates (mode overlap and a mode expansion in a closed box, no reflection model); an FDTD or EME run would pin them down. Severity does not depend on the exact value.
- Whether layer 2/0 (Si Slab) is offered on the run this chip goes to.
- The chip has no `opt_in_...` test labels at the top level. The intent does not ask for them, so I did not post this; if the chip goes through the SiEPIC automated test, labels are needed.
- Wavelength dependence (single wavelength 1.55 um), TM behaviour, and thermal effects were not checked.
