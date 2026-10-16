"""Heater calibration. The architect owns this file.

Requirements (tools/verify.py calls this routine on the nominal die and on each blind virtual die):
    calibrate(station) -> {heater_name: temperature rise in K}

`station` is a tools.measure.StationHandle:
    station.heaters            ["heater_1", "heater_2", ...], from bottom to top, then from left to right
    station.heater_positions   {name: (x, y) in um}
    station.wavelengths        the wavelengths of a measurement (um)
    station.paths              ["IN1->OUT1", ...]
    station.max_dT             the maximum temperature rise of one heater (K)
    station.budget, .calls     the number of measurements permitted on this die, and the number used
    station.measure(settings, wavelengths=None) -> {path: dB array}   (with noise; each call uses one measurement)

The routine gets only measurements, as on a prober. It must not read the errors of a die, the
seeds of the dies, or the internals of tools/. Develop it on the nominal die and on the training
dies (python tools/measure.py --die 0..19).
"""


def calibrate(station) -> dict:
    return {name: 0.0 for name in station.heaters}
