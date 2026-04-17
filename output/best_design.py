"""
design.py - Photonic device design file.
THE AGENT MODIFIES THIS FILE.

Current device: Waveguide Crossing
Platform: Silicon photonics, 220nm SOI, 1550nm
Metric: mode transmission power west->east - higher is better
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
DESIGN_HALF = 3.0  # um - half-extent of 6um x 6um design region

# Broadband sweep: 1.5 um -> 1.6 um, 11 points
WAVELENGTHS = np.linspace(1.5, 1.6, 11)
FREQUENCIES = td.C_0 / WAVELENGTHS

# ============================================================
# Materials
# ============================================================
Si = td.Medium.from_nk(n=3.47, k=0, freq=FREQUENCY)
SiO2 = td.Medium.from_nk(n=1.44, k=0, freq=FREQUENCY)

# ============================================================
# Feed Waveguides (defined outside create_simulation)
# ============================================================
west_wg = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(-1e3, -WG_WIDTH / 2, -WG_HEIGHT / 2),
        rmax=(-DESIGN_HALF, WG_WIDTH / 2, WG_HEIGHT / 2),
    ),
    medium=Si,
)
east_wg = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(DESIGN_HALF, -WG_WIDTH / 2, -WG_HEIGHT / 2),
        rmax=(1e3, WG_WIDTH / 2, WG_HEIGHT / 2),
    ),
    medium=Si,
)
south_wg = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(-WG_WIDTH / 2, -1e3, -WG_HEIGHT / 2),
        rmax=(WG_WIDTH / 2, -DESIGN_HALF, WG_HEIGHT / 2),
    ),
    medium=Si,
)
north_wg = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(-WG_WIDTH / 2, DESIGN_HALF, -WG_HEIGHT / 2),
        rmax=(WG_WIDTH / 2, 1e3, WG_HEIGHT / 2),
    ),
    medium=Si,
)

# ============================================================
# Source and Monitors (defined outside create_simulation)
# ============================================================
BUFFER = 2.0  # um - spacing between design region and source/monitor planes
MODE_PLANE_SIZE = (0, WG_WIDTH * 4, WG_HEIGHT * 6)

# Mode source in west waveguide, launching toward +x
source = td.ModeSource(
    center=(-DESIGN_HALF - BUFFER / 2, 0, 0),
    size=MODE_PLANE_SIZE,
    source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY / 20),
    direction="+",
    mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
    mode_index=0,
    name="input_mode",
)

# Mode monitor in east waveguide (broadband)
mode_monitor = td.ModeMonitor(
    center=(DESIGN_HALF + BUFFER / 2, 0, 0),
    size=MODE_PLANE_SIZE,
    freqs=list(FREQUENCIES),
    mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
    name="mode",
)

# Field profile for visualization
field_monitor = td.FieldMonitor(
    size=(td.inf, td.inf, 0),
    freqs=[FREQUENCY],
    name="field_xy",
)


def create_simulation() -> td.Simulation:
    """Build and return a Tidy3D simulation of the waveguide crossing."""

    # --- Structures ---
    structures = [west_wg, east_wg, south_wg, north_wg]

    # Asymmetric crossing: H arm is the MMI (propagation direction for metric).
    # V arm is narrower, minimizing its blockage of the H-arm mode.
    # Symmetry requirement x↔-x, y↔-y allows H and V arms to differ.
    h_w_mmi = 1.3
    h_mmi_half = 1.6
    v_w_mmi = 0.8
    v_mmi_half = 1.7
    n_taper = 60

    def make_profile(w_mmi, mmi_h):
        w_ctr = w_mmi / 2
        w_edge = WG_WIDTH / 2
        mhn = mmi_h / DESIGN_HALF
        def f(s):
            if abs(s) <= mhn:
                return w_ctr
            t = (abs(s) - mhn) / (1 - mhn)
            return w_ctr + (w_edge - w_ctr) * t * t
        return f

    h_profile = make_profile(h_w_mmi, h_mmi_half)
    v_profile = make_profile(v_w_mmi, v_mmi_half)

    # Horizontal arm (west <-> east) — the MMI
    xs = np.linspace(-DESIGN_HALF, DESIGN_HALF, n_taper)
    top = [(x, h_profile(x / DESIGN_HALF)) for x in xs]
    bot = [(x, -h_profile(x / DESIGN_HALF)) for x in xs[::-1]]
    structures.append(
        td.Structure(
            geometry=td.PolySlab(
                vertices=bot + top,
                slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2),
                axis=2,
            ),
            medium=Si,
        )
    )

    # Vertical arm (south <-> north) — narrower
    ys = np.linspace(-DESIGN_HALF, DESIGN_HALF, n_taper)
    right = [(v_profile(y / DESIGN_HALF), y) for y in ys]
    left = [(-v_profile(y / DESIGN_HALF), y) for y in ys[::-1]]
    structures.append(
        td.Structure(
            geometry=td.PolySlab(
                vertices=left + right,
                slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2),
                axis=2,
            ),
            medium=Si,
        )
    )

    sim_box = td.Box.from_bounds(
        rmin=(-DESIGN_HALF - BUFFER, -DESIGN_HALF - BUFFER, -1),
        rmax=(DESIGN_HALF + BUFFER, DESIGN_HALF + BUFFER, 1),
    )

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
    """Average mode transmission across 1.5-1.6 um (west -> east)."""

    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = np.abs(amp) ** 2

    return float(np.mean(T))
