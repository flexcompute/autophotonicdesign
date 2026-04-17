"""
design.py - Photonic device design file.
THE AGENT MODIFIES THIS FILE.

Current device: 3D Focusing Grating Coupler (220 nm SOI, 70 nm partial etch)
Platform: Silicon photonics, 1550 nm
Metric: fiber-to-chip coupling efficiency into the fundamental TE mode of a
500 nm strip waveguide.

Geometry
--------
Focal point at (x=0, y=0). A 500 nm strip waveguide extends in the -x direction
from the focal point. A linear triangular fan connects the 500 nm strip to the
inner edge of the grating, which is an angular sector around +x. The grating
teeth are confocal ellipses (one focus at the focal point) so that the tilted
incident beam couples coherently into a slab mode that converges at the focal
point and feeds the strip waveguide.

Each tooth lies on the locus satisfying the 3D grating condition
    n_eff * r  -  sin(theta) * x  =  m * lambda
(1st order, m=1). In polar form this is an ellipse with one focus at the origin
    r(phi) = r0 * (1 - e) / (1 - e * cos(phi)),     e = sin(theta) / n_eff
where r0 is the tooth's radius on the +x axis (phi=0).

2D-optimized knobs (reused here):
    angle = 34 deg, DC = 0.40 uniform, period chirp 0.733 -> 0.749 um,
    num_teeth = 25, beam_x = 0.41 * grating_radial_length.

3D-specific knobs (new):
    focal_length (r_1 on +x axis), angular_half_span_deg (arc extent),
    wg_width = 0.5 um (fixed by user).
"""

import numpy as np
import tidy3d as td


# ============================================================
# Device Parameters (fixed)
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

# Strip-waveguide stub length (mode monitor at x = -WG_LENGTH/2)
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
        rmin=(-1e3, -1e3, -1e3),
        rmax=(1e3, 1e3, -WG_HEIGHT / 2 - BOX_THICK),
    ),
    medium=Si,
)

BOX_AND_CLADDING = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(-1e3, -1e3, -WG_HEIGHT / 2 - BOX_THICK),
        rmax=(1e3, 1e3, WG_HEIGHT / 2 + CLAD_THICK),
    ),
    medium=SiO2,
)


def create_simulation() -> td.Simulation:
    """Build and return a 3D Tidy3D simulation of the focusing grating coupler."""

    # --- Tunable parameters (seeded from the 2D optimum) ---
    num_teeth = 25
    beam_angle_deg = 34.0        # beam tilt from vertical
    duty_cycle = 0.40            # uniform
    focal_length = 12.0          # um; r_1 on +x axis (inner tooth edge)
    angular_half_span_deg = 25.0 # tooth arc half-extent in phi
    wg_width = 0.5               # 500 nm strip waveguide

    # Chirped period (2D optimum was 0.733 -> 0.749)
    period_start = 0.733
    period_end = 0.749
    periods = np.linspace(period_start, period_end, num_teeth)

    # Tooth inner/outer radii on the +x axis (phi = 0)
    tooth_inner_r0 = focal_length + np.concatenate(([0.0], np.cumsum(periods[:-1])))
    tooth_outer_r0 = tooth_inner_r0 + duty_cycle * periods

    inner_r = float(tooth_inner_r0[0])
    outer_r = float(tooth_outer_r0[-1])
    grating_length_radial = outer_r - inner_r

    phi_max = np.deg2rad(angular_half_span_deg)
    beam_angle = np.deg2rad(beam_angle_deg)

    # Ellipse eccentricity (based on estimated slab-mode effective index in the
    # grating region; geometry is insensitive to small n_eff errors).
    n_eff_est = 4.00
    e_ecc = np.sin(beam_angle) / n_eff_est

    # Beam position on +x axis (reuse 2D shift: 41 % of grating radial length
    # from the inner edge).
    beam_x = inner_r + 0.41 * grating_length_radial

    # --- Helper functions ---
    def ellipse_r(r0, phi):
        """Ellipse radius at angle phi, with r(phi=0) = r0 and focus at origin."""
        return r0 * (1.0 - e_ecc) / (1.0 - e_ecc * np.cos(phi))

    def circular_sector_vertices(r_in, r_out, phi_half, n_points=60):
        """CCW polygon vertices for a circular annular sector."""
        phis_out = np.linspace(-phi_half, phi_half, n_points)
        phis_in = phis_out[::-1]
        pts = [(r_out * np.cos(p), r_out * np.sin(p)) for p in phis_out]
        pts += [(r_in * np.cos(p), r_in * np.sin(p)) for p in phis_in]
        return pts

    def elliptical_ring_vertices(r_in0, r_out0, phi_half, n_points=40):
        """CCW polygon vertices for an elliptical annular sector (tooth)."""
        phis_out = np.linspace(-phi_half, phi_half, n_points)
        phis_in = phis_out[::-1]
        pts = [
            (ellipse_r(r_out0, p) * np.cos(p), ellipse_r(r_out0, p) * np.sin(p))
            for p in phis_out
        ]
        pts += [
            (ellipse_r(r_in0, p) * np.cos(p), ellipse_r(r_in0, p) * np.sin(p))
            for p in phis_in
        ]
        return pts

    # --- Structures ---
    structures = [SUBSTRATE, BOX_AND_CLADDING]

    # 500 nm strip waveguide (full 220 nm Si) extending toward -x from the
    # focal point. Extended slightly past x=0 to overlap the fan polygon.
    structures.append(
        td.Structure(
            geometry=td.Box.from_bounds(
                rmin=(-100.0, -wg_width / 2, -WG_HEIGHT / 2),
                rmax=(0.1, wg_width / 2, WG_HEIGHT / 2),
            ),
            medium=Si,
        )
    )

    # Fan taper (220 nm Si) connecting the waveguide tip to the grating.
    # Outer boundary follows the first tooth's inner arc exactly (an ellipse
    # with r0 = inner_r), so the fan never intrudes past tooth 0's inner edge
    # and therefore cannot fill any gap between teeth.
    fan_phis = np.linspace(-phi_max, phi_max, 60)
    fan_outer_pts = [
        (ellipse_r(inner_r, p) * np.cos(p), ellipse_r(inner_r, p) * np.sin(p))
        for p in fan_phis
    ]
    fan_vertices = (
        [(0.0, -wg_width / 2)]
        + fan_outer_pts            # phi goes -phi_max -> +phi_max (CCW)
        + [(0.0, wg_width / 2)]
    )
    structures.append(
        td.Structure(
            geometry=td.PolySlab(
                vertices=fan_vertices,
                slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2),
                axis=2,
            ),
            medium=Si,
        )
    )

    # Un-etched 150 nm Si slab filling the grating angular sector. Inner radius
    # is pulled slightly inside the fan ellipse (which reaches its min at
    # phi=+/-phi_max) to guarantee the slab covers the full tooth-0 footprint.
    slab_inner = inner_r * (1.0 - e_ecc) / (1.0 - e_ecc * np.cos(phi_max)) - 0.1
    slab_vertices = circular_sector_vertices(
        slab_inner, outer_r + 0.5, phi_max, n_points=80
    )
    structures.append(
        td.Structure(
            geometry=td.PolySlab(
                vertices=slab_vertices,
                slab_bounds=(-WG_HEIGHT / 2, -WG_HEIGHT / 2 + SLAB_HEIGHT),
                axis=2,
            ),
            medium=Si,
        )
    )

    # Grating teeth: 70 nm of Si on top of the slab, lying on confocal
    # ellipses (one focus at origin).
    for i in range(num_teeth):
        tooth_vertices = elliptical_ring_vertices(
            float(tooth_inner_r0[i]),
            float(tooth_outer_r0[i]),
            phi_max,
            n_points=40,
        )
        structures.append(
            td.Structure(
                geometry=td.PolySlab(
                    vertices=tooth_vertices,
                    slab_bounds=(-WG_HEIGHT / 2 + SLAB_HEIGHT, WG_HEIGHT / 2),
                    axis=2,
                ),
                medium=Si,
            )
        )

    # --- Source: Gaussian beam from above, tilted toward the waveguide ---
    source = td.GaussianBeam(
        center=(beam_x, 0.0, BEAM_Z),
        size=(td.inf, td.inf, 0),  # injection plane normal to z
        source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FWIDTH),
        direction="-",
        angle_theta=-beam_angle,
        angle_phi=np.pi,  # tilt in -x direction (toward the waveguide)
        waist_radius=BEAM_WAIST,
        waist_distance=BEAM_Z - WG_HEIGHT / 2,  # waist near the grating surface
        pol_angle=np.pi / 2,  # E along y -> TE for the strip mode
        name="gauss",
    )

    # --- Monitors ---
    # Broadband mode-monitor frequencies: 31 points covering 1500-1600 nm.
    broadband_wavelengths = np.linspace(1.50, 1.60, 31)
    broadband_freqs = (td.C_0 / broadband_wavelengths).tolist()

    monitors = [
        # Mode monitor in the 500 nm strip waveguide (fundamental TE),
        # sampled at 31 wavelengths from 1500 to 1600 nm for broadband IL.
        td.ModeMonitor(
            center=(-WG_LENGTH / 2, 0.0, 0.0),
            size=(0, 4 * wg_width, 6 * WG_HEIGHT),
            freqs=broadband_freqs,
            mode_spec=td.ModeSpec(num_modes=1, target_neff=2.4),
            name="mode",
        ),
        # xz-slice at y=0 (kept name "field_xy" for compat with simulate.py).
        td.FieldMonitor(
            center=(0.0, 0.0, 0.0),
            size=(td.inf, 0, td.inf),
            freqs=[FREQUENCY],
            name="field_xy",
        ),
        # Top-down slice near the slab mid-plane to visualize focusing.
        td.FieldMonitor(
            center=(0.0, 0.0, -WG_HEIGHT / 2 + SLAB_HEIGHT / 2),
            size=(td.inf, td.inf, 0),
            freqs=[FREQUENCY],
            name="field_top",
        ),
    ]

    # --- Simulation domain ---
    buffer_xy = 1.5
    buffer_z_bot = 1.0
    buffer_z_top = 0.5

    sim_x_min = -WG_LENGTH - buffer_xy
    sim_x_max = outer_r + buffer_xy
    sim_y_max = outer_r * np.sin(phi_max) + buffer_xy + 1.0
    sim_y_min = -sim_y_max
    sim_z_min = -WG_HEIGHT / 2 - BOX_THICK - buffer_z_bot
    sim_z_max = BEAM_Z + buffer_z_top

    sim = td.Simulation(
        center=(
            (sim_x_min + sim_x_max) / 2,
            0.0,
            (sim_z_min + sim_z_max) / 2,
        ),
        size=(
            sim_x_max - sim_x_min,
            sim_y_max - sim_y_min,
            sim_z_max - sim_z_min,
        ),
        # 16 steps/wvl keeps a 3D run in the ~1-2 FlexCredit range; bump up for
        # the final polish runs.
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=WAVELENGTH),
        structures=structures,
        sources=[source],
        monitors=monitors,
        run_time=3e-12,
        medium=Air,  # air above the cladding
        boundary_spec=td.BoundarySpec(
            x=td.Boundary.pml(),
            y=td.Boundary.pml(),
            z=td.Boundary.pml(),
        ),
    )

    return sim


def evaluate(sim_data):
    """Coupling efficiency from the Gaussian beam into the strip-waveguide TE mode."""
    amp = sim_data["mode"].amps.sel(mode_index=0, direction="-").values
    return float(np.abs(amp[0]) ** 2)
