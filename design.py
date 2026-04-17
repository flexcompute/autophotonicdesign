"""
design.py - Photonic device design file.
THE AGENT MODIFIES THIS FILE.

Current device: Grating Coupler (2D, xz-plane)
Platform: Silicon photonics, 220nm SOI, 1550nm
Metric: fiber-to-chip coupling efficiency into the slab waveguide mode.
"""

import numpy as np
import tidy3d as td


# ============================================================
# Device Parameters
# ============================================================
WAVELENGTH = 1.55  # um - C-band center
FREQUENCY = td.C_0 / WAVELENGTH
FWIDTH = FREQUENCY / 10  # broader pulse for coupler response

# Silicon stack
WG_HEIGHT = 0.22  # um - standard SOI thickness
ETCH_DEPTH = 0.07  # um - partial etch
SLAB_HEIGHT = WG_HEIGHT - ETCH_DEPTH  # un-etched slab = 150 nm
CLAD_THICK = 2.0  # um - SiO2 top cladding
BOX_THICK = 2.0  # um - buried oxide

# Slab waveguide stub to the left of the grating
WG_LENGTH = 1.0  # um

# Gaussian beam source (approximating an SMF-28 fiber mode)
BEAM_WAIST = 5.2  # um (~MFD/2 of SMF-28)
BEAM_Z = WG_HEIGHT / 2 + CLAD_THICK + 0.3  # slightly above the cladding

# ============================================================
# Materials
# ============================================================
Si = td.Medium.from_nk(n=3.47, k=0, freq=FREQUENCY)
SiO2 = td.Medium.from_nk(n=1.44, k=0, freq=FREQUENCY)
Air = td.Medium()  # vacuum / air, background above the cladding


# ============================================================
# Fixed stack structures (substrate + BOX + cladding)
# ============================================================
SUBSTRATE = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(-1e3, -td.inf, -1e3),
        rmax=(1e3, td.inf, -WG_HEIGHT / 2 - BOX_THICK),
    ),
    medium=Si,
)

BOX_AND_CLADDING = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(-1e3, -td.inf, -WG_HEIGHT / 2 - BOX_THICK),
        rmax=(1e3, td.inf, WG_HEIGHT / 2 + CLAD_THICK),
    ),
    medium=SiO2,
)


def create_simulation() -> td.Simulation:
    """Build and return a 2D Tidy3D simulation of the grating coupler."""

    # --- Tunable parameters ---
    grating_period = 0.63  # um
    grating_duty_cycle = 0.5  # tooth width / period
    num_teeth = 25
    beam_angle_deg = 10.0  # Gaussian beam tilt from vertical (degrees)

    grating_length = num_teeth * grating_period
    beam_angle = np.deg2rad(beam_angle_deg)
    beam_x = grating_length / 2  # centered over the grating

    # --- Structures ---
    structures = [SUBSTRATE, BOX_AND_CLADDING]

    # Slab waveguide (full 220 nm Si) extending to the left of the grating
    structures.append(
        td.Structure(
            geometry=td.Box.from_bounds(
                rmin=(-1e3, -td.inf, -WG_HEIGHT / 2),
                rmax=(0, td.inf, WG_HEIGHT / 2),
            ),
            medium=Si,
        )
    )

    # Un-etched slab under the grating region (150 nm)
    structures.append(
        td.Structure(
            geometry=td.Box.from_bounds(
                rmin=(0, -td.inf, -WG_HEIGHT / 2),
                rmax=(grating_length, td.inf, -WG_HEIGHT / 2 + SLAB_HEIGHT),
            ),
            medium=Si,
        )
    )

    # Grating teeth on top of the slab
    tooth_width = grating_period * grating_duty_cycle
    for i in range(num_teeth):
        x0 = i * grating_period
        structures.append(
            td.Structure(
                geometry=td.Box.from_bounds(
                    rmin=(x0, -td.inf, -WG_HEIGHT / 2 + SLAB_HEIGHT),
                    rmax=(x0 + tooth_width, td.inf, WG_HEIGHT / 2),
                ),
                medium=Si,
            )
        )

    # --- Source: Gaussian beam from above, tilted toward the waveguide ---
    source = td.GaussianBeam(
        center=(beam_x, 0, BEAM_Z),
        size=(td.inf, td.inf, 0),  # injection plane normal to z
        source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FWIDTH),
        direction="-",
        angle_theta=-beam_angle,
        angle_phi=np.pi,  # tilt in -x direction (toward the waveguide)
        waist_radius=BEAM_WAIST,
        waist_distance=BEAM_Z - WG_HEIGHT / 2,  # beam waist near the grating surface
        pol_angle=np.pi / 2,  # E along y → TE polarization in the slab
        name="gauss",
    )

    # --- Monitors ---
    monitors = [
        # Mode monitor in the slab waveguide (captures coupled slab mode)
        td.ModeMonitor(
            center=(-WG_LENGTH / 2, 0, 0),
            size=(0, td.inf, 6 * WG_HEIGHT),
            freqs=[FREQUENCY],
            mode_spec=td.ModeSpec(num_modes=1, target_neff=2.8),
            name="mode",
        ),
        # Field profile for visualization
        td.FieldMonitor(
            size=(td.inf, 0, td.inf),
            freqs=[FREQUENCY],
            name="field_xz",
        ),
    ]

    # --- Simulation domain ---
    buffer_x = 1.5
    buffer_z_bot = 1.0
    buffer_z_top = 0.5

    sim_x_min = -WG_LENGTH - buffer_x
    sim_x_max = grating_length + buffer_x
    sim_z_min = -WG_HEIGHT / 2 - BOX_THICK - buffer_z_bot
    sim_z_max = BEAM_Z + buffer_z_top

    sim = td.Simulation(
        center=(
            (sim_x_min + sim_x_max) / 2,
            0,
            (sim_z_min + sim_z_max) / 2,
        ),
        size=(
            sim_x_max - sim_x_min,
            0,  # 2D simulation in xz-plane
            sim_z_max - sim_z_min,
        ),
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=WAVELENGTH),
        structures=structures,
        sources=[source],
        monitors=monitors,
        run_time=3e-12,
        medium=Air,  # air above the cladding
        boundary_spec=td.BoundarySpec(
            x=td.Boundary.pml(),
            y=td.Boundary.periodic(),
            z=td.Boundary.pml(),
        ),
    )

    return sim


def evaluate(sim_data):
    """Coupling efficiency from the Gaussian beam into the slab mode."""
    amp = sim_data["mode"].amps.sel(mode_index=0, direction="-").values
    return float(np.abs(amp[0]) ** 2)
