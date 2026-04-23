"""
design.py - Photonic device design file.
THE AGENT MODIFIES THIS FILE.

Current device: SiN edge coupler
Platform: air / 2 um SiO2 top clad / 400 nm SiN / 2 um SiO2 BOX / Si substrate
Wavelength: 1310 nm (O-band)
Metric: coupling efficiency from a 3.2 um MFD Gaussian beam into the
        fundamental TE mode of a 1 um-wide SiN waveguide - higher is better
"""

import numpy as np
import tidy3d as td


# ============================================================
# Device parameters
# ============================================================
WAVELENGTH = 1.31  # um
FREQUENCY = td.C_0 / WAVELENGTH

WG_WIDTH = 1.0  # um - bulk SiN waveguide width
WG_HEIGHT = 0.4  # um - SiN thickness (400 nm)
TAPER_LENGTH = 50.0  # um - fixed

BOX_THICKNESS = 2.0  # um - buried oxide
CLAD_THICKNESS = 2.0  # um - top SiO2 cladding
SUB_MARGIN = 2.0  # um - Si substrate portion included in sim
AIR_MARGIN = 2.0  # um - air region included in sim

MFD = 3.2  # um - Gaussian mode field diameter
WAIST_RADIUS = MFD / 2  # um - 1/e^2 field radius

BUFFER = 3.0  # um - padding between structures and sim edges


# ============================================================
# Materials (non-dispersive values near 1310 nm)
# ============================================================
SiN = td.Medium.from_nk(n=2.00, k=0, freq=FREQUENCY)
SiO2 = td.Medium.from_nk(n=1.447, k=0, freq=FREQUENCY)
Si = td.Medium.from_nk(n=3.504, k=0, freq=FREQUENCY)
Air = td.Medium(permittivity=1.0)


# ============================================================
# Vertical stack reference planes (SiN layer centered at z = 0)
# ============================================================
Z_SIN_BOT = -WG_HEIGHT / 2
Z_SIN_TOP = WG_HEIGHT / 2
Z_BOX_BOT = Z_SIN_BOT - BOX_THICKNESS
Z_CLAD_TOP = Z_SIN_TOP + CLAD_THICKNESS


# ============================================================
# Chip structures (background medium = Air).
# The chip facet is at x = 0 -- BOX, cladding and substrate only exist for
# x >= 0, leaving free space (air) on the input side of the facet.
# ============================================================
si_substrate = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(0.0, -1e3, -1e3),
        rmax=(1e3, 1e3, Z_BOX_BOT),
    ),
    medium=Si,
)

# Single SiO2 block covering BOX + in-plane SiN-layer fill + top cladding for x >= 0.
# SiN structures below override this in the core region.
chip_sio2 = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(0.0, -1e3, Z_BOX_BOT),
        rmax=(1e3, 1e3, Z_CLAD_TOP),
    ),
    medium=SiO2,
)

# 1 um-wide straight SiN waveguide past the taper
output_waveguide = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(TAPER_LENGTH, -WG_WIDTH / 2, Z_SIN_BOT),
        rmax=(1e3, WG_WIDTH / 2, Z_SIN_TOP),
    ),
    medium=SiN,
)


# ============================================================
# Source: Gaussian beam at the chip facet (outside the tip, +x launch)
# Source plane spans ~1.56 waists on each side (~99% of beam power).
# ============================================================
SRC_X = -BUFFER / 2

source = td.GaussianBeam(
    center=(SRC_X, 0, 0),
    size=(0, td.inf, td.inf),
    source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY / 20),
    direction="+",
    waist_radius=WAIST_RADIUS,
    waist_distance=0.0,
    pol_angle=0.0,  # E along y (TE-like)
    name="gaussian_in",
)


# ============================================================
# Monitors
# ============================================================
monitors = [
    td.ModeMonitor(
        center=(TAPER_LENGTH + BUFFER / 2, 0, 0),
        size=(0, 4 * WG_WIDTH, 4 * WG_HEIGHT + 2.0),
        freqs=[FREQUENCY],
        mode_spec=td.ModeSpec(num_modes=1, target_neff=1.72),
        name="mode",
    ),
    td.FieldMonitor(
        center=(0, 0, 0),
        size=(td.inf, td.inf, 0),
        freqs=[FREQUENCY],
        name="field_xy",
    ),
]


# ============================================================
# Simulation domain
# ============================================================
sim_box = td.Box.from_bounds(
    rmin=(
        -BUFFER,
        -(WG_WIDTH / 2 + BUFFER + WAIST_RADIUS),
        Z_BOX_BOT - SUB_MARGIN,
    ),
    rmax=(
        TAPER_LENGTH + BUFFER,
        WG_WIDTH / 2 + BUFFER + WAIST_RADIUS,
        Z_CLAD_TOP + AIR_MARGIN,
    ),
)


def create_simulation() -> td.Simulation:
    """Build and return a Tidy3D simulation of a 1310 nm SiN edge coupler.

    Parameters
    ----------
    tip_width : float
        Inverse-taper tip width at the chip facet, in microns. Design variable.
    """

    tip_width = 0.18

    # Inverse taper: narrow tip at facet (x=0), full width at x=TAPER_LENGTH
    taper_vertices = [
        (0.0, -tip_width / 2),
        (TAPER_LENGTH, -WG_WIDTH / 2),
        (TAPER_LENGTH, WG_WIDTH / 2),
        (0.0, tip_width / 2),
    ]
    taper = td.Structure(
        geometry=td.PolySlab(
            vertices=taper_vertices,
            slab_bounds=(Z_SIN_BOT, Z_SIN_TOP),
            axis=2,
        ),
        medium=SiN,
    )

    structures = [
        si_substrate,
        chip_sio2,
        taper,
        output_waveguide,
    ]

    sim = td.Simulation(
        center=sim_box.center,
        size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=18, wavelength=WAVELENGTH),
        structures=structures,
        sources=[source],
        monitors=monitors,
        run_time=4e-12,
        medium=Air,  # background = air (free space before the facet)
        symmetry=(0, -1, 0),  # y-mirror for TE-like Gaussian (E_y even)
    )

    return sim


def evaluate(sim_data):
    """Coupling efficiency: power coupled from the Gaussian source into
    the fundamental forward-propagating mode of the 1 um SiN waveguide."""

    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = np.abs(amp) ** 2
    return float(T[0])
