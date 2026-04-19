"""
design.py - Photonic device design file.
THE AGENT MODIFIES THIS FILE.

Current device: 1x2 Power Splitter
Platform: SiN photonics, 800nm SiN, 1310nm
Metric: total transmission power - higher is better
"""

import numpy as np
import tidy3d as td


# ============================================================
# Device Parameters
# ============================================================
WAVELENGTH = 1.31  # um - O-band
FREQUENCY = td.C_0 / WAVELENGTH
WG_WIDTH = 1.0  # um
WG_HEIGHT = 0.8  # um - SiN thickness
OUTPUT_SEPARATION = 3.0  # um - center-to-center of output waveguides
Y_BRANCH_LENGTH = 10  # um

# ============================================================
# Materials
# ============================================================
SiN = td.Medium.from_nk(n=2.0, k=0, freq=FREQUENCY)
SiO2 = td.Medium.from_nk(n=1.45, k=0, freq=FREQUENCY)

# ============================================================
# Fixed structures (input/output waveguides)
# ============================================================
INPUT_WG = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(-1e3, -WG_WIDTH / 2, -WG_HEIGHT / 2),
        rmax=(0, WG_WIDTH / 2, WG_HEIGHT / 2),
    ),
    medium=SiN,
)

OUTPUT_WG_UPPER = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(Y_BRANCH_LENGTH, OUTPUT_SEPARATION / 2 - WG_WIDTH / 2, -WG_HEIGHT / 2),
        rmax=(1e3, OUTPUT_SEPARATION / 2 + WG_WIDTH / 2, WG_HEIGHT / 2),
    ),
    medium=SiN,
)

OUTPUT_WG_LOWER = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(Y_BRANCH_LENGTH, -OUTPUT_SEPARATION / 2 - WG_WIDTH / 2, -WG_HEIGHT / 2),
        rmax=(1e3, -OUTPUT_SEPARATION / 2 + WG_WIDTH / 2, WG_HEIGHT / 2),
    ),
    medium=SiN,
)

# ============================================================
# Source, monitors, simulation box
# ============================================================
BUFFER = 2

SOURCE = td.ModeSource(
    center=(-BUFFER / 2, 0, 0),
    size=(0, WG_WIDTH * 3, WG_HEIGHT * 5),
    source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY / 20),
    direction="+",
    mode_spec=td.ModeSpec(num_modes=1, target_neff=2.0),
    mode_index=0,
    name="input_mode",
)

MONITORS = [
    td.ModeMonitor(
        center=(Y_BRANCH_LENGTH + BUFFER / 2, OUTPUT_SEPARATION / 2, 0),
        size=SOURCE.size,
        freqs=[FREQUENCY],
        mode_spec=td.ModeSpec(num_modes=1, target_neff=2.0),
        name="mode",
    ),
    td.FieldMonitor(
        size=(td.inf, td.inf, 0),
        freqs=[FREQUENCY],
        name="field_xy",
    ),
]

SIM_BOX = td.Box.from_bounds(
    rmin=(-BUFFER, -OUTPUT_SEPARATION / 2 - BUFFER, -1.5),
    rmax=(Y_BRANCH_LENGTH + BUFFER, OUTPUT_SEPARATION / 2 + BUFFER, 1.5),
)


def create_simulation() -> td.Simulation:
    """Build and return a Tidy3D simulation of the 1x2 splitter."""

    # Splitting junction — linear taper from input width to full output span
    junction_vertices = [
        (0, -WG_WIDTH / 2),
        (0, WG_WIDTH / 2),
        (Y_BRANCH_LENGTH, OUTPUT_SEPARATION / 2 + WG_WIDTH / 2),
        (Y_BRANCH_LENGTH, -OUTPUT_SEPARATION / 2 - WG_WIDTH / 2),
    ]
    junction = td.Structure(
        geometry=td.PolySlab(
            vertices=junction_vertices,
            slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2),
            axis=2,
        ),
        medium=SiN,
    )

    structures = [INPUT_WG, junction, OUTPUT_WG_UPPER, OUTPUT_WG_LOWER]

    sim = td.Simulation(
        center=SIM_BOX.center,
        size=SIM_BOX.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=WAVELENGTH),
        structures=structures,
        sources=[SOURCE],
        monitors=MONITORS,
        run_time=2e-12,
        medium=SiO2,  # cladding / background
        symmetry=(0, -1, 1),
    )

    return sim


def evaluate(sim_data):
    """Evaluate the excess loss of the 1x2 splitter."""

    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = np.abs(amp) ** 2

    return 10 * np.log10(2 * T[0])
