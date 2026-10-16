"""Tuning routine, only for a chip with tuning elements (spec.md has a tuning section). The architect owns this file.

Contract (tools/verify.py calls it on the nominal die and on every blind virtual die):
    calibrate(station) -> {heater_name: dT_in_K}

`station` is a tools.measure.StationHandle:
    station.heaters            ["heater_1", "heater_2", ...]  sorted bottom to top, then left to right
    station.heater_positions   {name: (x, y) um}
    station.wavelengths        the measurement grid (um)
    station.paths              ["IN1->OUT1", ...]
    station.max_dT             highest dT one heater accepts (K)
    station.budget, .calls     measurement budget for this die, and calls used so far
    station.measure(settings, wavelengths=None) -> {path: dB array}   (noisy, counts against the budget)

The routine sees only measurements, like a prober. It must not read the die's errors, the spec's
random seeds, or tools/ internals. Work it out on the nominal die and on the training dies
(python tools/measure.py --die 0..19).
"""


def calibrate(station) -> dict:
    return {name: 0.0 for name in station.heaters}
