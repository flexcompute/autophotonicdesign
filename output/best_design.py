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


def _cosine_arm_polygon(
    x0, x1, y_outer_0, y_outer_1, y_inner_0, y_inner_1, n_pts=80
):
    """Polygon for one access arm shaped by two cosine edges.

    Cosine-eased so the outer/inner edges are tangent (dy/dx = 0) at both ends.
    """
    xs = np.linspace(x0, x1, n_pts)
    t = (xs - x0) / (x1 - x0)
    eased = (1 - np.cos(np.pi * t)) / 2
    y_outer = y_outer_0 + (y_outer_1 - y_outer_0) * eased
    y_inner = y_inner_0 + (y_inner_1 - y_inner_0) * eased
    top = [(x, y) for x, y in zip(xs, y_outer)]
    bot = [(x, y) for x, y in zip(xs[::-1], y_inner[::-1])]
    return top + bot


def create_simulation() -> td.Simulation:
    """1x2 MMI splitter with tapered, cosine-S-bent access arms.

    Self-imaging: L_1x2 ≈ 3·Lπ/16, with Lπ = 4·n_eff·W_eff²/(3·λ).
    For W_mmi = 3.0 μm, n_slab ≈ 2.85, λ = 1.55 μm  →  L ≈ 4.1 μm.

    Access arms are single polygons with:
      - outer edge flush with MMI top (y = ±W_mmi/2) at the root, cosine-
        easing out to (OUTPUT_SEPARATION/2 ± WG_WIDTH/2) at the device exit;
      - inner edge starting at ±CENTER_GAP/2 (DRC-safe center trench) at the
        root, cosine-easing out to the single-mode output edge.
    This eliminates any sub-λ corner pockets.
    """

    device_length = 10.0     # total device length; device occupies x ∈ [0, 10]

    # MMI parameters
    mmi_width = 2.1           # um
    mmi_length = 3.65         # um — finetune sweep optimum
    center_gap = 0.20         # um — center trench (≥ 150 nm for DRC)

    # Input taper: match input WG mode to fundamental MMI mode
    in_taper_length = 1.5     # um
    in_taper_exit_w = 0.95    # um

    # x-layout inside [0, device_length]:
    x_taper_start = 0.0
    x_taper_end   = in_taper_length
    x_mmi_start   = x_taper_end
    x_mmi_end     = x_mmi_start + mmi_length
    x_arm_start   = x_mmi_end
    x_arm_end     = device_length

    structures = []

    # --- Input waveguide (before the device, x < 0) ---
    structures.append(
        td.Structure(
            geometry=td.Box.from_bounds(
                rmin=(-1e3, -WG_WIDTH / 2, -WG_HEIGHT / 2),
                rmax=(x_taper_start, WG_WIDTH / 2, WG_HEIGHT / 2),
            ),
            medium=Si,
        )
    )

    # --- Linear input taper: WG_WIDTH -> in_taper_exit_w over in_taper_length ---
    taper_verts = [
        (x_taper_start, -WG_WIDTH / 2),
        (x_taper_end,   -in_taper_exit_w / 2),
        (x_taper_end,    in_taper_exit_w / 2),
        (x_taper_start,  WG_WIDTH / 2),
    ]
    structures.append(
        td.Structure(
            geometry=td.PolySlab(
                vertices=taper_verts,
                slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2),
                axis=2,
            ),
            medium=Si,
        )
    )

    # --- MMI body (rectangular) ---
    structures.append(
        td.Structure(
            geometry=td.Box.from_bounds(
                rmin=(x_mmi_start, -mmi_width / 2, -WG_HEIGHT / 2),
                rmax=(x_mmi_end,    mmi_width / 2,  WG_HEIGHT / 2),
            ),
            medium=Si,
        )
    )

    # --- Access arms (upper and lower), single tapered S-bend polygons ---
    y_outer_root = mmi_width / 2                         # flush with MMI top
    y_inner_root = center_gap / 2                        # center trench wall
    y_outer_exit = OUTPUT_SEPARATION / 2 + WG_WIDTH / 2  # single-mode WG top
    y_inner_exit = OUTPUT_SEPARATION / 2 - WG_WIDTH / 2  # single-mode WG bottom

    upper_verts = _cosine_arm_polygon(
        x0=x_arm_start,
        x1=x_arm_end,
        y_outer_0=y_outer_root,
        y_outer_1=y_outer_exit,
        y_inner_0=y_inner_root,
        y_inner_1=y_inner_exit,
    )
    structures.append(
        td.Structure(
            geometry=td.PolySlab(
                vertices=upper_verts,
                slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2),
                axis=2,
            ),
            medium=Si,
        )
    )
    lower_verts = [(x, -y) for (x, y) in upper_verts]
    structures.append(
        td.Structure(
            geometry=td.PolySlab(
                vertices=lower_verts,
                slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2),
                axis=2,
            ),
            medium=Si,
        )
    )

    # --- Output extension waveguides past device end ---
    for sign in (+1, -1):
        structures.append(
            td.Structure(
                geometry=td.Box.from_bounds(
                    rmin=(device_length, sign * OUTPUT_SEPARATION / 2 - WG_WIDTH / 2, -WG_HEIGHT / 2),
                    rmax=(1e3, sign * OUTPUT_SEPARATION / 2 + WG_WIDTH / 2, WG_HEIGHT / 2),
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
            center=(device_length + buffer / 2, OUTPUT_SEPARATION / 2, 0),
            size=source.size,
            freqs=[FREQUENCY],
            mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
            name="mode",
        ),
        td.FieldMonitor(
            size=(td.inf, td.inf, 0),
            freqs=[FREQUENCY],
            name="field_xy",
        ),
    ]

    sim_box = td.Box.from_bounds(
        rmin=(-buffer, -OUTPUT_SEPARATION / 2 - buffer, -1),
        rmax=(device_length + buffer, OUTPUT_SEPARATION / 2 + buffer, 1),
    )

    sim = td.Simulation(
        center=sim_box.center,
        size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=30, wavelength=WAVELENGTH),
        structures=structures,
        sources=[source],
        monitors=monitors,
        run_time=2e-12,
        medium=SiO2,
        symmetry=(0, -1, 1),
    )

    return sim


def evaluate(sim_data):
    """Evaluate the total mode transmission of the 1x2 splitter."""

    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = np.abs(amp) ** 2

    return 2 * T[0]
