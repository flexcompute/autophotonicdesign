# Spec: two-channel heated lattice demux (SiPhoPDK, O-band)

The person who wants the chip writes this file and `spec.yaml`. The team does not change them.
If a target is not possible, the team says so with evidence (see program.md, "Escalate").

## Function

A 2-channel wavelength demultiplexer with flat-top pass bands, made as a heated MZI lattice
(directional couplers and delay arms, with heaters on the arms).

- Light enters at **IN1**. Channel A (1310 nm) leaves at **OUT1**. Channel B (1315 nm) leaves at **OUT2**.
- **IN2** is the second input of the first coupler. Bring it out to a grating coupler; it is not scored.
- Heaters set the phases of the lattice and correct die-to-die variation. Each heater connects
  to two bond pads, named `H<k>P` and `H<k>N` (k = 1, 2, ...).

## Targets (fiber to fiber, grating couplers included)

| | Nominal die | Each virtual die |
|---|---|---|
| Pass band | center +- 1.5 nm | same |
| Ripple in the pass band | <= 1.0 dB | <= 1.5 dB |
| Worst insertion loss in the pass band | <= 4.5 dB | <= 5.0 dB |
| Isolation: worst pass level minus worst level in the other channel's band (+- 1.0 nm) | >= 15 dB | >= 10 dB |
| Center of the 1-dB band | within +- 0.5 nm | same |
| Sum of heater rises after calibration | <= 20 K | (heater limit 75 K each) |

Both channels must meet the targets: channel A on IN1->OUT1, channel B on IN1->OUT2.

## Variation and calibration

Every die differs from the drawing: an n_eff error on every waveguide piece (whole-die offset,
a gradient across the die, local noise) and an error on every coupler (gap variation).
The sigmas are in `spec.yaml` under `variation`.

The team writes `design/tuning.py: calibrate(station)`. It gets only measurements, like a
prober, with **60 measurements per die**. The final check runs it on **8 blind dies** (new random
dies every run) and needs **75%** of them to pass. Dies 0 to 19 are for training.

## Layout

- PDK: SiPhoPDK (`tools/pdks/siphopdk.py`). Use its cells. New cells only when no PDK cell fits.
- Die: whole chip inside **440 x 480 um**. Grating couplers on a 127 um fiber-array pitch, all
  facing one edge.
- DRC clean and LVS clean on the PDK decks. No metal on a heater's layer may cross another net.

## Limits on the work

- Cloud FDTD is allowed only when the PDK has no model for a part. Keep each run small and log it
  (`python tools/team.py log --event cloud --cost <FC>`). The checks (`tools/verify.py`) are
  offline and free.
- Finish in one session. No long simulations.
