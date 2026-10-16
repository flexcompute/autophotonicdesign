# Spec: tunable 2-channel lattice demux, O-band, SiPhoPDK

## Request

Build a tunable 2-channel lattice filter in the O-band with 5 nm channel spacing.

## Function

- Light goes into IN1. Channel A (1310 nm) goes out at OUT1. Channel B (1315 nm) goes out at OUT2.
- IN2 is the second input of the first coupler. Connect IN2 to a grating coupler. The tools do not score IN2.
- The filter is a heated MZI lattice: directional couplers, delay arms, and heaters on the arms.
- The heaters set the phases of the lattice. The heaters also correct the variation between dies.
- Connect each heater to two bond pads. Name the pads H<k>P and H<k>N (k = 1, 2, ...).
- Use PDK cells. Make a new cell only if no PDK cell can do the function.
- All losses are fiber to fiber. The grating couplers are part of the chip.

## Defaults

The request does not give these values. The lead selected them.

| Value | Default | Reason |
|---|---|---|
| PDK | SiPhoPDK | default PDK of this repository |
| Channel A center | 1310 nm | peak of the SiPhoPDK grating coupler |
| Channel B center | 1315 nm | channel A plus the 5 nm channel spacing |
| Pass band | center +/- 1.5 nm | 30% of the channel spacing |
| Stop band | center of the other channel +/- 1.0 nm | 20% of the channel spacing |
| Targets, die size, variation, measurement budget | template values | the request does not give them |

## Numbers

The tools read only this block. The lead writes it. The human approves it. After the approval,
no agent changes it.

```yaml
name: tunable 2-channel lattice demux
pdk: siphopdk                       # adapter in tools/pdks/<pdk>.py

layout:
  max_size: [440.0, 480.0]          # um, bounding box of the full chip (x, y)
  optical_ports: [IN1, IN2, OUT1, OUT2]   # top-level ports at the fiber side of the grating couplers
  heater_terminals: true            # each heater connects to two top-level terminals H<k>P and H<k>N

simulation:
  band: [1.300, 1.320]              # um
  points: 401
  paths: [[IN1, OUT1], [IN1, OUT2]] # (input, output) pairs that the test station measures

tuning:                             # optional: delete this section for a chip with no tuning elements
  type: thermal                     # heaters (thermo-optic phase shifters)
  max_dT: 75.0                      # K, maximum temperature rise of one heater
  nominal_total_dT_max: 20.0        # K, maximum sum of the heater rises on the nominal die

metrics:                            # each metric runs on the nominal die and on each virtual die
  - name: channel_A
    path: [IN1, OUT1]
    type: channel                   # function in tools/metrics.py
    args: {center: 1.310, pass_halfwidth: 0.0015, stop_offsets: [0.005], stop_halfwidth: 0.0010}
    nominal: {ripple_db: {max: 1.0}, insertion_loss_db: {max: 4.5}, isolation_db: {min: 15.0}, center_error_nm: {abs_max: 0.5}}
    die:     {ripple_db: {max: 1.5}, insertion_loss_db: {max: 5.0}, isolation_db: {min: 10.0}, center_error_nm: {abs_max: 0.5}}
  - name: channel_B
    path: [IN1, OUT2]
    type: channel
    args: {center: 1.315, pass_halfwidth: 0.0015, stop_offsets: [-0.005], stop_halfwidth: 0.0010}
    nominal: {ripple_db: {max: 1.0}, insertion_loss_db: {max: 4.5}, isolation_db: {min: 15.0}, center_error_nm: {abs_max: 0.5}}
    die:     {ripple_db: {max: 1.5}, insertion_loss_db: {max: 5.0}, isolation_db: {min: 10.0}, center_error_nm: {abs_max: 0.5}}

variation:                          # virtual dies in tools/measure.py; values are one standard deviation
  dies: 8                           # blind dies in the final check (new random dies at each run)
  pass_fraction: 0.75               # fraction of blind dies that must meet all 'die' targets (after calibrate(), if the chip has tuning)
  training_dies: 20                 # dies 0 to 19: the team can use them for development
  n_eff:
    global: 0.003                   # offset of the full die (film thickness, mean width)
    gradient_per_um: 5.0e-6         # linear change across the die, in x and in y
    local: 2.0e-4                   # independent error of each waveguide piece
  coupler_length_scale:             # error of the full-transfer length of each coupler (gap variation)
    global: 0.03
    local: 0.01

measurement:
  budget_per_die: 60                # maximum number of station.measure() calls for one die
  noise_db: 0.05
  floor_db: -50.0
```

## Metric definitions (tools/metrics.py, type `channel`)

- Pass band: center +/- pass_halfwidth. Stop band: (center + offset) +/- stop_halfwidth.
- insertion_loss_db: the highest loss in the pass band.
- ripple_db: the maximum minus the minimum in the pass band.
- isolation_db: the lowest level in the pass band minus the highest level in the stop band.
- center_error_nm: the center of the 1-dB band minus the specified center.

## Limits on the work

- Use cloud FDTD only for a part that has no model in the PDK. Keep each run small. Log the cost.
- The checks in tools/ run on this computer. They do not use FlexCredits.
- Do not run a simulation that takes more than 10 minutes.
