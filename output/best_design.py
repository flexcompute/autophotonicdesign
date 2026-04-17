"""
design.py - Photonic device design file.
THE AGENT MODIFIES THIS FILE.

Current device: Waveguide Taper (0.5 um -> 5 um)
Platform: Silicon photonics, 220nm SOI, 1550nm
Metric: fundamental mode transmission - higher is better
"""

import numpy as np
import tidy3d as td


# ============================================================
# Device Parameters
# ============================================================
WAVELENGTH = 1.55  # um - C-band center
FREQUENCY = td.C_0 / WAVELENGTH
WG_WIDTH_IN = 0.5  # um - input waveguide (single-mode)
WG_WIDTH_OUT = 5.0  # um - output waveguide (multi-mode)
WG_HEIGHT = 0.22  # um - standard SOI thickness
TAPER_LENGTH = 6.0  # um - fixed taper length

# ============================================================
# Materials
# ============================================================
Si = td.Medium.from_nk(n=3.47, k=0, freq=FREQUENCY)
SiO2 = td.Medium.from_nk(n=1.44, k=0, freq=FREQUENCY)

# ============================================================
# Input / Output waveguides (fixed)
# ============================================================
input_wg = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(-1e3, -WG_WIDTH_IN / 2, -WG_HEIGHT / 2),
        rmax=(0, WG_WIDTH_IN / 2, WG_HEIGHT / 2),
    ),
    medium=Si,
)

output_wg = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(TAPER_LENGTH, -WG_WIDTH_OUT / 2, -WG_HEIGHT / 2),
        rmax=(1e3, WG_WIDTH_OUT / 2, WG_HEIGHT / 2),
    ),
    medium=Si,
)

# ============================================================
# Source and monitor (fixed)
# ============================================================
BUFFER = 1.0

source = td.ModeSource(
    center=(-BUFFER / 2, 0, 0),
    size=(0, WG_WIDTH_IN * 4, WG_HEIGHT * 6),
    source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY / 20),
    direction="+",
    mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
    mode_index=0,
    name="input_mode",
)

mode_monitor = td.ModeMonitor(
    center=(TAPER_LENGTH + BUFFER / 2, 0, 0),
    size=(0, WG_WIDTH_OUT + 2, WG_HEIGHT * 6),
    freqs=[FREQUENCY],
    mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
    name="mode",
)

field_monitor = td.FieldMonitor(
    size=(td.inf, td.inf, 0),
    freqs=[FREQUENCY],
    name="field_xy",
)

# ============================================================
# Simulation domain (fixed)
# ============================================================
sim_box = td.Box.from_bounds(
    rmin=(-BUFFER, -WG_WIDTH_OUT / 2 - BUFFER, -1),
    rmax=(TAPER_LENGTH + BUFFER, WG_WIDTH_OUT / 2 + BUFFER, 1),
)


def create_simulation() -> td.Simulation:
    """Build and return a Tidy3D simulation of the waveguide taper."""

    # --- Autograd-optimized taper: 120 narrow + 40 step widths + endpoints.
    # Scaled up from 80+25 to break out of the 0.972 plateau.
    xb = 5.9
    M_narrow = 120
    M_step = 40
    x_narrow = np.linspace(TAPER_LENGTH / (M_narrow + 1), xb * M_narrow / (M_narrow + 1), M_narrow)
    x_step = np.linspace(xb + (TAPER_LENGTH - xb) / (M_step + 1), TAPER_LENGTH - (TAPER_LENGTH - xb) / (M_step + 1), M_step)
    x_ctrl = np.concatenate([[0.0], x_narrow, [xb], x_step, [TAPER_LENGTH]])
    w_narrow_step = np.array([
        0.69592, 0.87708, 1.04623, 1.18223, 1.29310, 1.38047, 1.44753, 1.49551,
        1.52541, 1.54107, 1.55207, 1.55911, 1.56855, 1.57741, 1.58582, 1.59365,
        1.60157, 1.60958, 1.61783, 1.62642, 1.63530, 1.64453, 1.65399, 1.66380,
        1.67506, 1.68679, 1.69890, 1.71155, 1.72492, 1.73889, 1.75315, 1.76758,
        1.78232, 1.79872, 1.81727, 1.83975, 1.87399, 1.91216, 1.95242, 1.99434,
        2.03564, 2.07491, 2.10762, 2.13374, 2.15598, 2.17442, 2.19151, 2.20753,
        2.22168, 2.23489, 2.24753, 2.25956, 2.27100, 2.28212, 2.29299, 2.30364,
        2.31425, 2.32497, 2.33598, 2.34724, 2.35891, 2.37361, 2.39142, 2.41298,
        2.44006, 2.47024, 2.50425, 2.54245, 2.58253, 2.62384, 2.66379, 2.70156,
        2.73588, 2.76230, 2.78470, 2.80419, 2.82083, 2.83687, 2.85314, 2.87050,
        2.89333, 2.92719, 2.96555, 3.00594, 3.04834, 3.08374, 3.11328, 3.13552,
        3.15203, 3.16740, 3.18247, 3.19788, 3.21576, 3.23787, 3.26731, 3.30193,
        3.34028, 3.37765, 3.41333, 3.44610, 3.47561, 3.50409, 3.53204, 3.56105,
        3.59104, 3.62156, 3.65267, 3.68392, 3.71464, 3.73759, 3.75555, 3.76857,
        3.77778, 3.78619, 3.79390, 3.80121, 3.80845, 3.81563, 3.82276, 3.82974,
        3.83655,
        3.85386, 3.87115, 3.88844, 3.90573, 3.92302, 3.94035, 3.95768, 3.97502,
        3.99238, 4.01040, 4.02899, 4.04876, 4.07024, 4.09436, 4.12038, 4.14917,
        4.18575, 4.22833, 4.27619, 4.33378, 4.39649, 4.45922, 4.52189, 4.58450,
        4.64697, 4.70628, 4.76310, 4.81326, 4.84433, 4.86703, 4.88553, 4.90260,
        4.91804, 4.93245, 4.94589, 4.95750, 4.96365, 4.96742, 4.96910, 4.97505])
    w_ctrl = np.concatenate([[WG_WIDTH_IN], w_narrow_step, [WG_WIDTH_OUT]])
    N = 601
    xs = np.linspace(0.0, TAPER_LENGTH, N)
    ws = np.interp(xs, x_ctrl, w_ctrl)

    upper = [(float(x), float(w / 2)) for x, w in zip(xs, ws)]
    lower = [(float(x), float(-w / 2)) for x, w in zip(xs[::-1], ws[::-1])]
    taper_vertices = upper + lower

    taper = td.Structure(
        geometry=td.PolySlab(
            vertices=taper_vertices,
            slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2),
            axis=2,
        ),
        medium=Si,
    )

    structures = [input_wg, taper, output_wg]

    # --- Simulation ---
    sim = td.Simulation(
        center=sim_box.center,
        size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=WAVELENGTH),
        structures=structures,
        sources=[source],
        monitors=[mode_monitor, field_monitor],
        run_time=2e-12,
        medium=SiO2,  # cladding / background
        symmetry=(0, -1, 1),
    )

    return sim


def evaluate(sim_data):
    """Evaluate the fundamental mode transmission of the taper."""

    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = np.abs(amp) ** 2

    return T[0]
