"""
design.py - Photonic device design file.
THE AGENT MODIFIES THIS FILE.

Current device: 90-degree waveguide bend
Platform: SiN-on-SiO2, 400 nm thickness, 1200 nm width, 1550 nm
Metric: mode transmission through the bend - higher is better
"""

import numpy as np
import tidy3d as td


# ============================================================
# Device Parameters
# ============================================================
WAVELENGTH = 1.55  # um - C-band center
FREQUENCY = td.C_0 / WAVELENGTH
WG_WIDTH = 1.2  # um - SiN waveguide width
WG_HEIGHT = 0.4  # um - SiN film thickness
BEND_RADIUS = 12.0  # um - fixed 90-deg bend radius

# ============================================================
# Materials
# ============================================================
SiN = td.Medium.from_nk(n=2.0, k=0, freq=FREQUENCY)
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
    medium=SiN,
)

# Vertical output waveguide: runs along +y at x=BEND_RADIUS, starts at y=BEND_RADIUS
vertical_wg = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(BEND_RADIUS - WG_WIDTH / 2, BEND_RADIUS, -WG_HEIGHT / 2),
        rmax=(BEND_RADIUS + WG_WIDTH / 2, 1e3, WG_HEIGHT / 2),
    ),
    medium=SiN,
)

# ============================================================
# Source and monitor (fixed, outside create_simulation)
# ============================================================
BUFFER = 1.5  # um - padding between structures and PML / source planes

# Mode source in the horizontal waveguide, launching toward +x
source = td.ModeSource(
    center=(-BUFFER / 2, 0, 0),
    size=(0, WG_WIDTH * 3, WG_HEIGHT * 5),
    source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY / 20),
    direction="+",
    mode_spec=td.ModeSpec(num_modes=1, target_neff=2.0),
    mode_index=0,
    name="input_mode",
)

# Mode monitor in the vertical waveguide, measuring the +y-going mode
mode_monitor = td.ModeMonitor(
    center=(BEND_RADIUS, BEND_RADIUS + BUFFER / 2, 0),
    size=(WG_WIDTH * 3, 0, WG_HEIGHT * 5),
    freqs=[FREQUENCY],
    mode_spec=td.ModeSpec(num_modes=1, target_neff=2.0),
    name="mode",
)


def _curvature_profile_centerline(profile_fn, endpoint=(BEND_RADIUS, BEND_RADIUS),
                                  N: int = 1601):
    """90-deg centerline whose curvature K(u) ∝ profile_fn(u) on u in [0, 1].

    Scales so theta(0)=0, theta(L)=π/2, and (xc[-1], yc[-1]) == endpoint.
    """
    u = np.linspace(0.0, 1.0, N)
    f = profile_fn(u)
    F = np.concatenate(([0.0], np.cumsum(0.5 * (f[:-1] + f[1:]) * np.diff(u))))
    theta = F * (np.pi / 2) / F[-1]
    cs = np.cos(theta)
    ss = np.sin(theta)
    du = np.diff(u)
    dx = 0.5 * (cs[:-1] + cs[1:]) * du
    dy = 0.5 * (ss[:-1] + ss[1:]) * du
    xc_u = np.concatenate(([0.0], np.cumsum(dx)))
    yc_u = np.concatenate(([0.0], np.cumsum(dy)))
    L = endpoint[0] / xc_u[-1]
    return xc_u * L, yc_u * L, theta


def _euler_centerline(p: float, endpoint=(BEND_RADIUS, BEND_RADIUS), N: int = 801):
    """Clothoid-arc-clothoid 90-deg centerline from (0, 0) to endpoint.

    p in [0, 1]: fraction of the 90-deg swept by the two clothoids.
        p = 0  -> pure circular arc of radius endpoint[0]
        p = 1  -> pure Euler (two clothoids joining in the middle)
    Returns (x, y, theta).  theta is the tangent angle.
    """
    if p <= 1e-6:
        theta = np.linspace(0.0, np.pi / 2, N)
        R = endpoint[0]
        return R * np.sin(theta), R * (1.0 - np.cos(theta)), theta

    s1 = 1.0
    theta1 = p * np.pi / 4
    theta2 = np.pi / 2 - theta1
    Kmax = 2.0 * theta1 / s1
    arc_len = (theta2 - theta1) / Kmax
    s_mid_end = s1 + arc_len
    L = 2.0 * s1 + arc_len

    s = np.linspace(0.0, L, N)
    theta = np.empty_like(s)
    m1 = s <= s1
    theta[m1] = theta1 * (s[m1] / s1) ** 2
    m2 = (s > s1) & (s <= s_mid_end)
    theta[m2] = theta1 + Kmax * (s[m2] - s1)
    m3 = s > s_mid_end
    sm = L - s[m3]
    theta[m3] = np.pi / 2 - theta1 * (sm / s1) ** 2

    cs = np.cos(theta)
    ss = np.sin(theta)
    dx = 0.5 * (cs[:-1] + cs[1:]) * np.diff(s)
    dy = 0.5 * (ss[:-1] + ss[1:]) * np.diff(s)
    xc = np.concatenate(([0.0], np.cumsum(dx)))
    yc = np.concatenate(([0.0], np.cumsum(dy)))

    scale = endpoint[0] / xc[-1]
    return xc * scale, yc * scale, theta


def _bend_polyslab(xc, yc, theta, width):
    """Build PolySlab vertices for a waveguide swept along (xc, yc) with
    tangent angle theta.  `width` may be a scalar or an array of the same
    length as xc (per-sample width for tapering).
    """
    nx = -np.sin(theta)    # left-hand normal (points toward bend center for a left turn)
    ny = np.cos(theta)
    w = np.asarray(width, dtype=float) / 2.0
    if w.ndim == 0:
        w = np.full_like(xc, float(w))
    inner = np.stack([xc + w * nx, yc + w * ny], axis=1)     # toward bend center
    outer = np.stack([xc - w * nx, yc - w * ny], axis=1)     # away from bend center

    # CCW polygon: forward along outer, then backward along inner
    verts = [tuple(p) for p in outer] + [tuple(p) for p in inner[::-1]]
    return verts


def create_simulation() -> td.Simulation:
    """Build and return a Tidy3D simulation of the 90-deg waveguide bend."""

    # --- Euler + width taper + inward radial offset ---
    p_euler = 0.45
    w_ratio = 2.0
    r_offset = -1.1   # negative = inward (toward bend center) at midpoint
    xc, yc, theta = _euler_centerline(p_euler, endpoint=(BEND_RADIUS, BEND_RADIUS))
    u = np.linspace(0.0, 1.0, len(xc))
    widths = WG_WIDTH * (1.0 + (w_ratio - 1.0) * np.sin(np.pi * u) ** 2)
    shift = r_offset * np.sin(np.pi * u) ** 2
    xc = xc + shift * np.sin(theta)
    yc = yc - shift * np.cos(theta)
    bend_vertices = _bend_polyslab(xc, yc, theta, widths)

    bend = td.Structure(
        geometry=td.PolySlab(
            vertices=bend_vertices,
            slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2),
            axis=2,
        ),
        medium=SiN,
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
        rmin=(-BUFFER, -WG_WIDTH / 2 - BUFFER, -1.5),
        rmax=(BEND_RADIUS + WG_WIDTH / 2 + BUFFER, BEND_RADIUS + BUFFER, 1.5),
    )

    sim = td.Simulation(
        center=sim_box.center,
        size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=40, wavelength=WAVELENGTH),
        structures=structures,
        sources=[source],
        monitors=[mode_monitor, field_monitor],
        run_time=3e-12,
        medium=SiO2,  # cladding / background
        symmetry=(0, 0, 1),  # TE mode symmetry about z=0
    )

    return sim


def evaluate(sim_data):
    """Evaluate the mode transmission through the bend."""

    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = np.abs(amp) ** 2

    return float(T[0])
