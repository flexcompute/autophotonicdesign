"""
design.py - Photonic device design file.
THE AGENT MODIFIES THIS FILE.

Current device: 90-degree waveguide bend
Platform: Silicon photonics, 220nm SOI, 1550nm
Metric: mode transmission through the bend - higher is better
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
BEND_RADIUS = 3.0  # um - fixed 90-deg bend radius

# ============================================================
# Materials
# ============================================================
Si = td.Medium.from_nk(n=3.47, k=0, freq=FREQUENCY)
SiO2 = td.Medium.from_nk(n=1.44, k=0, freq=FREQUENCY)

# ============================================================
# I/O waveguides (fixed, outside create_simulation)
# ============================================================
# Horizontal input waveguide: runs along +x at y=0, ends at x=0
horizontal_wg = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(-1e3, -WG_WIDTH / 2, -WG_HEIGHT / 2),
        rmax=(0, WG_WIDTH / 2, WG_HEIGHT / 2),
    ),
    medium=Si,
)

# Vertical output waveguide: runs along +y at x=BEND_RADIUS, starts at y=BEND_RADIUS
vertical_wg = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(BEND_RADIUS - WG_WIDTH / 2, BEND_RADIUS, -WG_HEIGHT / 2),
        rmax=(BEND_RADIUS + WG_WIDTH / 2, 1e3, WG_HEIGHT / 2),
    ),
    medium=Si,
)

# ============================================================
# Source and monitor (fixed, outside create_simulation)
# ============================================================
BUFFER = 1.0  # um - padding between structures and PML / source planes

# Mode source in the horizontal waveguide, launching toward +x
source = td.ModeSource(
    center=(-BUFFER / 2, 0, 0),
    size=(0, WG_WIDTH * 4, WG_HEIGHT * 6),
    source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY / 20),
    direction="+",
    mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
    mode_index=0,
    name="input_mode",
)

# Mode monitor in the vertical waveguide, measuring the +y-going mode
mode_monitor = td.ModeMonitor(
    center=(BEND_RADIUS, BEND_RADIUS + BUFFER / 2, 0),
    size=(WG_WIDTH * 4, 0, WG_HEIGHT * 6),
    freqs=[FREQUENCY],
    mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
    name="mode",
)


def create_simulation() -> td.Simulation:
    """Build and return a Tidy3D simulation of the 90-deg waveguide bend."""

    # --- Circular bend structure ---
    # Arc centered at (0, BEND_RADIUS), sweeping from angle -pi/2 to 0.
    # This connects (0, 0) on the horizontal WG to (BEND_RADIUS, BEND_RADIUS)
    # on the vertical WG.
    num_arc_points = 64
    angles = np.linspace(-np.pi / 2, 0.0, num_arc_points)
    r_outer = BEND_RADIUS + WG_WIDTH / 2
    r_inner = BEND_RADIUS - WG_WIDTH / 2

    outer_vertices = [
        (r_outer * np.cos(a), BEND_RADIUS + r_outer * np.sin(a)) for a in angles
    ]
    inner_vertices = [
        (r_inner * np.cos(a), BEND_RADIUS + r_inner * np.sin(a))
        for a in angles[::-1]
    ]
    bend_vertices = outer_vertices + inner_vertices

    bend = td.Structure(
        geometry=td.PolySlab(
            vertices=bend_vertices,
            slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2),
            axis=2,
        ),
        medium=Si,
    )

    structures = [horizontal_wg, vertical_wg, bend]

    # --- Field monitor for visualization ---
    field_monitor = td.FieldMonitor(
        size=(td.inf, td.inf, 0),
        freqs=[FREQUENCY],
        name="field_xy",
    )

    # --- Simulation domain ---
    sim_box = td.Box.from_bounds(
        rmin=(-BUFFER, -WG_WIDTH / 2 - BUFFER, -1),
        rmax=(BEND_RADIUS + WG_WIDTH / 2 + BUFFER, BEND_RADIUS + BUFFER, 1),
    )

    sim = td.Simulation(
        center=sim_box.center,
        size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=WAVELENGTH),
        structures=structures,
        sources=[source],
        monitors=[mode_monitor, field_monitor],
        run_time=2e-12,
        medium=SiO2,  # cladding / background
        symmetry=(0, 0, 1),  # TE mode symmetry about z=0
    )

    return sim


def evaluate(sim_data):
    """Evaluate the mode transmission through the bend."""

    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = np.abs(amp) ** 2

    return float(T[0])
