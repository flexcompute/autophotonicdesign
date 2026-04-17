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

    # --- Taper structure (linear by default; the agent may modify this) ---
    taper_vertices = [
        (0, -WG_WIDTH_IN / 2),
        (0, WG_WIDTH_IN / 2),
        (TAPER_LENGTH, WG_WIDTH_OUT / 2),
        (TAPER_LENGTH, -WG_WIDTH_OUT / 2),
    ]
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
