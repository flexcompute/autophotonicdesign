"""
design.py - Photonic device design file.
THE AGENT MODIFIES THIS FILE.

Current device: 1x2 Power Splitter
Platform: Silicon photonics, 220nm SOI, 1550nm
Metric: total transmission power - higher is better
"""

import numpy as np
import tidy3d as td


# ============================================================
# Device Parameters
# ============================================================
WAVELENGTH = 1.55  # um - C-band center
FREQUENCY = td.C_0 / WAVELENGTH
WG_WIDTH = 0.5  # um - single-mode at 1550nm
WG_HEIGHT = 0.22  # um - standard SOI thickness
OUTPUT_SEPARATION = 2.0  # um - center-to-center of output waveguides

# ============================================================
# Materials
# ============================================================
Si = td.Medium.from_nk(n=3.47, k=0, freq=FREQUENCY)
SiO2 = td.Medium.from_nk(n=1.44, k=0, freq=FREQUENCY)


def create_simulation() -> td.Simulation:
    """Build and return a Tidy3D simulation of the 1x2 splitter."""

    # --- Structures ---
    structures = []

    # Input waveguide
    structures.append(
        td.Structure(
            geometry=td.Box.from_bounds(
                rmin=(-1e3, -WG_WIDTH / 2, -WG_HEIGHT / 2),
                rmax=(0, WG_WIDTH / 2, WG_HEIGHT / 2),
            ),
            medium=Si,
        )
    )

    taper_length = 10

    # Splitting junction — linear taper from input width to full output span
    junction_vertices = [
        (0, -WG_WIDTH / 2),
        (0, WG_WIDTH / 2),
        (taper_length, OUTPUT_SEPARATION / 2 + WG_WIDTH / 2),
        (taper_length, -OUTPUT_SEPARATION / 2 - WG_WIDTH / 2),
    ]
    structures.append(
        td.Structure(
            geometry=td.PolySlab(
                vertices=junction_vertices,
                slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2),
                axis=2,
            ),
            medium=Si,
        )
    )

    # Output waveguide 1 (upper, +y)
    structures.append(
        td.Structure(
            geometry=td.Box.from_bounds(
                rmin=(
                    taper_length,
                    OUTPUT_SEPARATION / 2 - WG_WIDTH / 2,
                    -WG_HEIGHT / 2,
                ),
                rmax=(1e3, OUTPUT_SEPARATION / 2 + WG_WIDTH / 2, WG_HEIGHT / 2),
            ),
            medium=Si,
        )
    )

    # Output waveguide 2 (lower, -y)
    structures.append(
        td.Structure(
            geometry=td.Box.from_bounds(
                rmin=(
                    taper_length,
                    -OUTPUT_SEPARATION / 2 - WG_WIDTH / 2,
                    -WG_HEIGHT / 2,
                ),
                rmax=(1e3, -OUTPUT_SEPARATION / 2 + WG_WIDTH / 2, WG_HEIGHT / 2),
            ),
            medium=Si,
        )
    )

    buffer = 2
    # --- Source ---
    source = td.ModeSource(
        center=(-buffer / 2, 0, 0),
        size=(0, WG_WIDTH * 4, WG_HEIGHT * 6),
        source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY / 20),
        direction="+",
        mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
        mode_index=0,
        name="input_mode",
    )

    # --- Monitors ---
    monitors = [
        td.ModeMonitor(
            center=(taper_length + buffer / 2, OUTPUT_SEPARATION / 2, 0),
            size=source.size,
            freqs=[FREQUENCY],
            mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
            name="mode",
        ),
        # Field profile for visualization
        td.FieldMonitor(
            size=(td.inf, td.inf, 0),
            freqs=[FREQUENCY],
            name="field_xy",
        ),
    ]

    sim_box = td.Box.from_bounds(
        rmin=(-buffer, -OUTPUT_SEPARATION / 2 - buffer, -1),
        rmax=(taper_length + buffer, OUTPUT_SEPARATION / 2 + buffer, 1),
    )

    # --- Simulation ---
    sim = td.Simulation(
        center=sim_box.center,
        size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=WAVELENGTH),
        structures=structures,
        sources=[source],
        monitors=monitors,
        run_time=2e-12,
        medium=SiO2,  # cladding / background
        symmetry=(0, -1, 1),
    )

    return sim


def evaluate(sim_data):
    """Evaluate the total mode transmission of the 1x2 splitter."""

    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = np.abs(amp) ** 2

    return 2 * T[0]
