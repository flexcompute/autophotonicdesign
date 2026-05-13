"""
design.py — Segmented CPW (T-rail) electrode for a TFLN/TFLT Mach–Zehnder modulator.

THE AGENT MODIFIES THIS FILE.

Replicates the geometry of CPWRFPhotonics2.ipynb (T-rail loaded CPW) and exposes
the design knobs that matter for an autoresearch loop:

  • T-electrode geometry (s, r, h, t, c)            — the slow-wave loading
  • CPW dimensions (g, ws, wg)                       — the host CPW
  • Metal thickness (tm) and conductivity            — conductor loss
  • Cladding permittivity / thickness (eps_clad,
    tsio21)                                          — dielectric environment
  • TFLN slab/rib thicknesses (tln0, tln1)           — anisotropic layer

Targets at f_REF = 67 GHz on a TFLT/TFLN MZM platform:

  • RF index n_eff    ≈  2.20    (match optical group index of TE @1310 nm)
  • Impedance |Z0|    ≈  50 Ω    (matched to drive electronics)
  • RF loss α₀         minimized in dB/cm/√GHz units (skin-effect-dominated)

Length units are micrometres throughout, frequencies in Hz.
"""

from __future__ import annotations

import numpy as np
import tidy3d as td
import tidy3d.rf as rf

# ============================================================
# Frequency band  (do not edit — fixed for the loop)
# ============================================================
F_MIN = 1e9
F_MAX = 50e9          # capped below the wave-port excitation artifact band
F_REF = 40e9          # reference frequency for headline metrics — mid-band
F_FIT_MIN = 5e9       # skin-loss fit window — avoids low-f and band-edge artifacts
F_FIT_MAX = 45e9
N_FREQS = 51          # 51 points over the band
FREQS = np.linspace(F_MIN, F_MAX, N_FREQS)
F0 = (F_MIN + F_MAX) / 2

# ============================================================
# >>>> AGENT-TUNABLE DESIGN PARAMETERS <<<<
# ============================================================
# Layer thicknesses (μm)
TM = 1.0               # metal thickness
TSIO21 = 0.2           # SiO2 cladding above LN
TSIO20 = 2.0           # SiO2 BOX
TLN0 = 0.6             # TFLN un-etched (rib top)
TLN1 = 0.3             # TFLN etched (slab)

# Cladding & substrate permittivities  (TFLN o-/e- and gold are baseline-frozen)
EPS_CLAD = 3.8         # SiO2 cladding+BOX permittivity at RF
EPS_QZ = 4.5           # quartz substrate permittivity at RF
EPS_LN_O = 44.0        # TFLN ordinary
EPS_LN_EO = 27.9       # TFLN extraordinary
SIGMA_AU_S_per_um = 41.0   # gold conductivity (S/μm)

# CPW dimensions (μm) — host CPW (signal trace + ground rails)
G = 5.0                # CPW gap
WS = 100.0             # signal trace width
WG = 300.0             # ground trace width

# T-electrode dimensions (μm) — the slow-wave loading geometry
T_S = 2.0              # width of T top (along propagation)
T_R = 45.0             # length of T top (transverse)
T_H = 6.0              # length of T neck (transverse, into gap)
T_T = 2.0              # width of T neck (along propagation)
T_C = 5.0              # gap between adjacent T units (along propagation)

# Optical waveguide (μm) — frozen by the photonic platform
W0 = 1.0               # rib top width
THETA_LN_DEG = 30.0    # rib sidewall angle

# Run-budget knobs (3-D segmented sim cost scales ~linearly with N_PERIODS)
N_PERIODS = 20         # number of T-rail unit cells in the simulated section
N_PAD_PERIODS = 5      # input/output conventional-CPW lengths, in T-rail periods
MIN_STEPS_PER_WVL = 12 # FDTD grid (notebook 3-D used 20; 12 is faster, noisier)
WP_OFFSET = 100.0      # μm setback of each wave port from the segmented region

# ============================================================
# Mediums (built from the editable permittivities above)
# ============================================================
MED_AIR = td.Medium(permittivity=1.0, name="Air")
MED_CLAD = td.Medium(permittivity=EPS_CLAD, name="SiO2")
MED_SUB = td.Medium(permittivity=EPS_QZ, name="Quartz")
MED_LN_O = td.Medium(permittivity=EPS_LN_O, name="TFLN ord.")
MED_LN_EO = td.Medium(permittivity=EPS_LN_EO, name="TFLN extraord.")
MED_LN = td.AnisotropicMedium(xx=MED_LN_EO, yy=MED_LN_O, zz=MED_LN_O, name="TFLN")
MED_AU = rf.LossyMetalMedium(
    conductivity=SIGMA_AU_S_per_um,
    frequency_range=(F_MIN, F_MAX),
    name="Gold",
)

# ============================================================
# Derived geometry (do not edit)
# ============================================================
LEN_INF = 1e5
P_T = T_R + T_C                       # T-rail period along propagation
GW = G + 2 * (T_S + T_H)              # widened CPW gap including T-rails
W_CPW = WS + 2 * (G + WG)             # overall span of conventional CPW
W1 = 1000.0                           # transverse extent of dielectric layers

LTL = N_PERIODS * P_T                 # length of segmented section
L_IN = N_PAD_PERIODS * P_T            # length of input conventional CPW
L_OUT = N_PAD_PERIODS * P_T           # length of output conventional CPW

THETA_LN_RAD = np.deg2rad(THETA_LN_DEG)


# ============================================================
# Geometry builders
# ============================================================
def _dielectric_layers():
    """Quartz / BOX / TFLN slab / SiO2 cladding stack (cross-section is uniform in y)."""
    qz_thickness = LEN_INF
    str_clad = td.Structure(
        medium=MED_CLAD,
        geometry=td.Box(
            center=(0, 0, (TLN0 - TLN1) + TSIO21 / 2.0),
            size=(W1, td.inf, TSIO21),
        ),
    )
    str_box = td.Structure(
        medium=MED_CLAD,
        geometry=td.Box(center=(0, 0, -TSIO20 / 2.0), size=(W1, td.inf, TSIO20)),
    )
    str_qz = td.Structure(
        medium=MED_SUB,
        geometry=td.Box(
            center=(0, 0, -qz_thickness / 2.0 + TSIO20 / 2 - TM / 2),
            size=(W1, td.inf, qz_thickness),
        ),
    )
    str_ln = td.Structure(
        medium=MED_LN,
        geometry=td.Box(center=(0, 0, TLN1 / 2.0), size=(W1, td.inf, TLN1)),
    )
    return [str_qz, str_clad, str_box, str_ln]


def _create_rib(width, height, sidewall_angle, center, medium):
    """Mirrored pair of rib waveguides for the two MZM arms."""
    x0, y0 = center
    geom1 = td.PolySlab(
        axis=2,
        sidewall_angle=sidewall_angle,
        reference_plane="top",
        slab_bounds=(y0 - height / 2, y0 + height / 2),
        vertices=[
            (x0 + width / 2, LEN_INF),
            (x0 - width / 2, LEN_INF),
            (x0 - width / 2, -LEN_INF),
            (x0 + width / 2, -LEN_INF),
        ],
    )
    geom2 = geom1.translated(-2 * x0, 0, 0)
    return td.Structure(geometry=td.GeometryGroup(geometries=[geom1, geom2]), medium=medium)


def _create_cpw_traces(gap, signal_w, ground_w, thickness, y_start, y_end):
    """Three parallel metal traces (left ground, signal, right ground) running in y."""
    length = y_end - y_start
    midpos = (y_end + y_start) / 2.0
    z_metal = TLN0 - TLN1 + TSIO21 + thickness / 2.0
    return [
        td.Structure(
            medium=MED_AU,
            geometry=td.Box(
                size=(ground_w, length, thickness),
                center=(-signal_w / 2 - gap - ground_w / 2, midpos, z_metal),
            ),
        ),
        td.Structure(
            medium=MED_AU,
            geometry=td.Box(
                size=(ground_w, length, thickness),
                center=(signal_w / 2 + gap + ground_w / 2, midpos, z_metal),
            ),
        ),
        td.Structure(
            medium=MED_AU,
            geometry=td.Box(
                size=(signal_w, length, thickness),
                center=(0, midpos, z_metal),
            ),
        ),
    ]


def _create_T(base_position, direction, width_r, width_t, width_s, width_h):
    """Single T-rail electrode (top + neck) anchored on a CPW edge."""
    x0, y0 = base_position
    sgn = 1 if direction == "+" else -1
    z_metal = TLN0 - TLN1 + TSIO21 + TM / 2.0
    return [
        td.Box(
            size=(width_s, width_r, TM),
            center=(x0 + sgn * (width_h + width_s / 2), y0, z_metal),
        ),
        td.Box(
            size=(width_h, width_t, TM),
            center=(x0 + sgn * width_h / 2, y0, z_metal),
        ),
    ]


def _segmented_section():
    """The cap-loaded (segmented) CPW + bracketing input/output conventional CPW + ribs."""
    # Ribs ride the right-hand CPW gap (single MZM arm view).
    rib_core = _create_rib(W0, TLN0 - TLN1, THETA_LN_RAD,
                           ((WS + GW) / 2, TLN0 - TLN1 / 2.0), MED_LN)
    rib_clad = _create_rib(1.2 * W0, TLN0 - TLN1, THETA_LN_RAD,
                           ((WS + GW) / 2, TLN0 - TLN1 / 2.0 + TSIO21), MED_CLAD)

    # Wide CPW spans the full segmented section (gap = GW). Ground rail
    # is shrunk by (T_S + T_H) so the outer edge stays in the same place
    # as the conventional CPW.
    cpw_wide = _create_cpw_traces(GW, WS, WG - (T_S + T_H), TM, -LEN_INF, LEN_INF)

    # Narrow CPW for input + output sections (gap = G).
    cpw_narrow = (
        _create_cpw_traces(G, WS + 2 * (T_S + T_H), WG, TM, -LEN_INF, -LTL / 2)
        + _create_cpw_traces(G, WS + 2 * (T_S + T_H), WG, TM, LTL / 2, LEN_INF)
    )

    # T-rail array — one period per row, four T's per row (two on each gap edge).
    t_geoms = []
    for ii in range(N_PERIODS + 1):
        yy = -LTL / 2 + ii * P_T
        # outer-left ground / signal-left edge / signal-right edge / outer-right ground
        edges_x = (-WS / 2 - GW, -WS / 2, WS / 2, WS / 2 + GW)
        directions = ("+", "-", "+", "-")
        for x_edge, direction in zip(edges_x, directions):
            t_geoms += _create_T((x_edge, yy), direction, T_R, T_T, T_S, T_H)
    t_struct = td.Structure(medium=MED_AU, geometry=td.GeometryGroup(geometries=t_geoms))

    return [rib_core, rib_clad, t_struct] + cpw_wide + cpw_narrow


# ============================================================
# Simulation builders
# ============================================================
def _grid_spec_3d():
    """Coarser corner refinement (dl=TM) for the 3-D segmented run — cost-bounded.

    Mirrors `LR_spec_2` in CPWRFPhotonics2.ipynb.
    """
    layer_refinement = rf.LayerRefinementSpec(
        center=(0, 0, TLN0 - TLN1 + TSIO21 + TM / 2.0),
        size=(td.inf, td.inf, TM),
        axis=2,
        corner_refinement=td.GridRefinement(dl=TM, num_cells=2),
        refinement_inside_sim_only=False,
    )
    rib_override = td.MeshOverrideStructure(
        geometry=td.Box(
            center=((WS + GW) / 2, 0, TLN1 / 2),
            size=(1.2 * W0, td.inf, TLN1),
        ),
        dl=(W0 / 5.0, None, TLN0 / 2),
    )
    return td.GridSpec.auto(
        wavelength=td.C_0 / F_MAX,
        min_steps_per_wvl=MIN_STEPS_PER_WVL,
        override_structures=[rib_override],
        layer_refinement_specs=[layer_refinement],
    )


def _grid_spec_2d(cpw_traces):
    """Finer corner refinement (dl=TM/5) for the cheap 2-D mode solver.

    Mirrors `LR_spec_1` in CPWRFPhotonics2.ipynb. Anchored on the actual CPW
    metal trace structures to make sure every conductor corner gets resolved.
    """
    layer_refinement = rf.LayerRefinementSpec.from_structures(
        structures=cpw_traces,
        min_steps_along_axis=5,
        refinement_inside_sim_only=False,
        corner_refinement=td.GridRefinement(dl=TM / 5.0, num_cells=2),
    )
    rib_override = td.MeshOverrideStructure(
        geometry=td.Box(
            center=((WS + G) / 2, 0, TLN1 / 2),
            size=(1.2 * W0, td.inf, TLN1),
        ),
        dl=(W0 / 5.0, None, TLN1 / 5.0),
    )
    return td.GridSpec.auto(
        wavelength=td.C_0 / F_MAX,
        min_steps_per_wvl=MIN_STEPS_PER_WVL,
        override_structures=[rib_override],
        layer_refinement_specs=[layer_refinement],
    )


def _wave_ports():
    """Two wave ports in the conventional input / output CPW sections."""
    padding = td.C_0 / F_MAX / 4
    sim_lx = W_CPW + 2 * padding
    wp_size = (sim_lx - 15, 0, sim_lx - 15)
    wp1 = rf.WavePort(
        name="WP1",
        center=(0, -LTL / 2 - WP_OFFSET, 1.0),
        size=wp_size,
        mode_spec=rf.MicrowaveModeSpec(target_neff=np.sqrt(8)),
        direction="+",
    )
    wp2 = wp1.updated_copy(
        name="WP2",
        center=(0, LTL / 2 + WP_OFFSET, 1.0),
        direction="-",
    )
    return wp1, wp2


def create_simulation() -> td.Simulation:
    """Build the 3-D segmented-CPW Tidy3D simulation (no wave ports attached)."""
    padding = td.C_0 / F_MAX / 4
    sim_lx = W_CPW + 2 * padding
    sim_lz = sim_lx
    sim_size = (sim_lx, LTL + L_IN + L_OUT, sim_lz)
    sim_center = (0, -(L_IN - L_OUT) / 2, 0)

    structures = _dielectric_layers() + _segmented_section()

    # Field monitor in the metal plane for visualization.
    mon_field = td.FieldMonitor(
        center=(0, 0, 1.0),
        size=(W_CPW, td.inf, 0),
        freqs=[F_MIN, F0, F_MAX],
        name="field cpw plane",
    )

    return td.Simulation(
        center=sim_center,
        size=sim_size,
        grid_spec=_grid_spec_3d(),
        structures=structures,
        monitors=[mon_field],
        run_time=2e-10,
        symmetry=(1, 0, 0),
    )


def create_modeler() -> rf.TerminalComponentModeler:
    """Wrap the simulation in a TCM for two-port S-parameter extraction."""
    sim = create_simulation()
    wp1, wp2 = _wave_ports()
    return rf.TerminalComponentModeler(
        simulation=sim,
        ports=[wp1, wp2],
        freqs=FREQS,
    )


def create_2d_modesolver_simulation() -> td.Simulation:
    """Cheap 2-D mode analysis on the *conventional* CPW (no T-rails).

    Used for sanity-checking the host-CPW Z0 / n_eff before paying for the
    full 3-D segmented run. Mirrors the "Conventional MZM-CPW (2D Analysis)"
    section of CPWRFPhotonics2.ipynb.
    """
    padding = td.C_0 / F_MAX / 4
    sim_lx = W_CPW + 2 * padding
    sim_size = (sim_lx, sim_lx, sim_lx)

    rib_core = _create_rib(W0, TLN0 - TLN1, THETA_LN_RAD,
                           ((WS + G) / 2, TLN0 - TLN1 / 2.0), MED_LN)
    rib_clad = _create_rib(1.2 * W0, TLN0 - TLN1, THETA_LN_RAD,
                           ((WS + G) / 2, TLN0 - TLN1 / 2.0 + TSIO21), MED_CLAD)
    cpw = _create_cpw_traces(G, WS, WG, TM, -LEN_INF, LEN_INF)
    structures = _dielectric_layers() + [rib_clad, rib_core] + cpw

    return td.Simulation(
        size=sim_size,
        medium=MED_AIR,
        grid_spec=_grid_spec_2d(cpw),
        structures=structures,
        symmetry=(1, 0, 0),
        run_time=1e-10,
    )


def create_2d_mode_solver():
    """ModeSolver for the conventional CPW (2-D)."""
    sim = create_2d_modesolver_simulation()
    padding = td.C_0 / F_MAX / 4
    sim_lx = W_CPW + 2 * padding
    wp_size = (sim_lx - 15, 0, sim_lx - 15)
    wp_dummy = rf.WavePort(
        center=(0, 0, 1.0),
        size=wp_size,
        mode_spec=rf.MicrowaveModeSpec(target_neff=np.sqrt(8)),
        direction="+",
        name="Dummy WP",
    )
    return wp_dummy.to_mode_solver(simulation=sim, freqs=FREQS)


# ============================================================
# Metric / FOM extraction
# ============================================================
def _line_extract_from_S21(s21, length_um, freqs_hz):
    """Uniform-line extraction from S21 only — robust at low |S11|.

    Treats the port-to-port path as a single propagation line of given length.
    Returns (alpha_dB_per_cm, n_eff, gamma) where gamma = α + jβ in 1/μm.

    |S21| > 1 (numerical noise on a passive line) is clipped to 1 so that α
    is non-negative.
    """
    s21 = np.asarray(s21, dtype=complex)
    abs_s21 = np.minimum(np.abs(s21), 1.0)
    phase_s21 = np.unwrap(np.angle(s21))
    alpha_Np_per_um = -np.log(abs_s21 + 1e-30) / length_um
    beta_rad_per_um = -phase_s21 / length_um

    alpha_dB_per_cm = 20.0 * np.log10(np.e) * alpha_Np_per_um * 1e4
    omega = 2.0 * np.pi * np.asarray(freqs_hz)
    # td.C_0 is already in μm/s (≈ 2.998e14), so no unit conversion needed.
    n_eff = beta_rad_per_um * td.C_0 / omega
    gamma = alpha_Np_per_um + 1j * beta_rad_per_um
    return alpha_dB_per_cm, n_eff, gamma


def _Z0_from_S(s11, s21, z_ref=50.0, abs_s11_floor=1e-3):
    """Characteristic impedance via Nicolson–Ross–Weir, guarded for low |S11|.

    For |S11| below the floor the line is essentially matched to z_ref, so
    we report Z0 = z_ref + 0j there to avoid 1/0.
    """
    s11 = np.asarray(s11, dtype=complex)
    s21 = np.asarray(s21, dtype=complex)
    Z0 = np.full_like(s11, complex(z_ref, 0.0))
    mask = np.abs(s11) > abs_s11_floor
    if mask.any():
        s11m = s11[mask]
        s21m = s21[mask]
        K_val = (s11m**2 - s21m**2 + 1) / (2 * s11m)
        K_sqrt = np.sqrt(K_val * K_val - 1)
        Gp = K_val + K_sqrt
        Gm = K_val - K_sqrt
        Gamma = np.where(np.abs(Gp) <= 1, Gp, Gm)
        Z0_m = z_ref * (1 + Gamma) / (1 - Gamma)
        Z0[mask] = Z0_m
    return Z0


def _fit_skin_loss(freqs_hz, alpha_dB_per_cm, f_min_hz=F_FIT_MIN, f_max_hz=F_FIT_MAX):
    """Fit α(f) = α₀·√f + α_offset over [f_min_hz, f_max_hz].

    Restricted window dodges mode-tracking artifacts at the band edges.
    α₀ is reported in dB/cm/√GHz.
    """
    freqs_hz = np.asarray(freqs_hz)
    alpha = np.asarray(alpha_dB_per_cm)
    mask = (freqs_hz >= f_min_hz) & (freqs_hz <= f_max_hz)
    f_GHz = freqs_hz[mask] / 1e9
    sqrt_f = np.sqrt(f_GHz)
    A = np.vstack([sqrt_f, np.ones_like(sqrt_f)]).T
    coeffs, *_ = np.linalg.lstsq(A, alpha[mask], rcond=None)
    return float(coeffs[0]), float(coeffs[1])


def evaluate(tcm_data, length_um=None):
    """Compute headline transmission-line metrics + scalar FOM from TCM data.

    Uses a uniform-line approximation across the full WP1→WP2 path
    (segmented section + the two short conventional CPW pads bracketing it).
    The segmented region dominates the path length (LTL / L_total ≈ 5/6),
    so the extracted n_eff and α track the segmented values within a few %.
    """
    if length_um is None:
        length_um = LTL + 2.0 * WP_OFFSET   # full WP1→WP2 distance, μm
    smat = tcm_data.smatrix()
    s11 = np.conjugate(smat.data.isel(port_in=0, port_out=0)).values.squeeze()
    s21 = np.conjugate(smat.data.isel(port_in=0, port_out=1)).values.squeeze()

    alpha_dBcm, n_eff, gamma = _line_extract_from_S21(s21, length_um, FREQS)
    Z0 = _Z0_from_S(s11, s21)

    # ---- Distributed-line RLCG params (per mm) ---------------------
    # γ = α + jβ (in 1/μm) and Z₀ together give the lumped-line equivalent.
    # Convert to per-mm so values land in nice human ranges:
    #   R  ~ Ω / mm     L  ~ nH / mm
    #   G  ~ S / mm     C  ~ pF / mm
    omega = 2.0 * np.pi * FREQS
    Z0_safe = np.where(np.abs(Z0) > 1e-3, Z0, complex(50.0, 0.0))
    R_per_um = np.real(gamma * Z0_safe)
    L_per_um = np.imag(gamma * Z0_safe) / omega
    G_per_um = np.real(gamma / Z0_safe)
    C_per_um = np.imag(gamma / Z0_safe) / omega
    R_per_mm = R_per_um * 1e3                # Ω/mm
    L_per_mm = L_per_um * 1e3                # H/mm  (display in nH)
    G_per_mm = G_per_um * 1e3                # S/mm
    C_per_mm = C_per_um * 1e3                # F/mm  (display in pF)

    # Headline numbers at f = F_REF (mid-band, clean of port-mode artifacts).
    n_eff_ref = float(np.interp(F_REF, FREQS, np.real(n_eff)))
    alpha_ref = float(np.interp(F_REF, FREQS, alpha_dBcm))
    Z0_ref = complex(np.interp(F_REF, FREQS, np.real(Z0)),
                     np.interp(F_REF, FREQS, np.imag(Z0)))
    R_ref  = float(np.interp(F_REF, FREQS, R_per_mm))
    L_ref  = float(np.interp(F_REF, FREQS, L_per_mm))
    G_ref  = float(np.interp(F_REF, FREQS, G_per_mm))
    C_ref  = float(np.interp(F_REF, FREQS, C_per_mm))

    alpha_0, alpha_offset = _fit_skin_loss(FREQS, alpha_dBcm)

    # Composite FOM (higher = better).  Quadratic penalties around the
    # impedance and index targets, linear reward for low loss.
    target_Z = 50.0
    target_n = 2.20
    lam_Z = 5.0
    lam_n = 50.0
    Z_term = lam_Z * ((Z0_ref.real - target_Z) / target_Z) ** 2
    n_term = lam_n * ((n_eff_ref - target_n) / target_n) ** 2
    fom = -(alpha_0 + Z_term + n_term)

    return {
        "metric": fom,
        "alpha_0_dBcm_per_sqrtGHz": alpha_0,
        "alpha_offset_dBcm": alpha_offset,
        "alpha_at_Fref_dBcm": alpha_ref,
        "Z0_real_at_Fref": Z0_ref.real,
        "Z0_imag_at_Fref": Z0_ref.imag,
        "n_eff_at_Fref": n_eff_ref,
        "R_Ohm_per_mm_at_Fref": R_ref,
        "L_nH_per_mm_at_Fref":  L_ref * 1e9,   # H/mm → nH/mm
        "G_S_per_mm_at_Fref":   G_ref,
        "C_pF_per_mm_at_Fref":  C_ref * 1e12,  # F/mm → pF/mm
        "F_ref_GHz": F_REF / 1e9,
        "FOM": fom,
        # Full sweep arrays (for plotting in simulate.py + npz archival).
        "_freqs_Hz": FREQS,
        "_alpha_dBcm": alpha_dBcm,
        "_n_eff": np.real(n_eff),
        "_Z0": Z0,
        "_S11": s11,
        "_S21": s21,
        "_gamma": gamma,
        "_R_per_mm": R_per_mm,        # Ω/mm
        "_L_per_mm": L_per_mm,        # H/mm
        "_G_per_mm": G_per_mm,        # S/mm
        "_C_per_mm": C_per_mm,        # F/mm
    }


def snapshot_header():
    """One-line text snapshot of the agent's current design knobs (for the journal)."""
    return (
        f"T(s={T_S},r={T_R},h={T_H},t={T_T},c={T_C}) "
        f"CPW(g={G},ws={WS},wg={WG}) "
        f"tm={TM} eps_clad={EPS_CLAD} tln0={TLN0} tln1={TLN1}"
    )


if __name__ == "__main__":
    # Smoke test: just instantiate, print a summary.
    sim = create_simulation()
    print("design.py — segmented CPW build summary")
    print(f"  knobs       : {snapshot_header()}")
    print(f"  sim size    : {tuple(round(s, 2) for s in sim.size)} μm")
    print(f"  structures  : {len(sim.structures)}")
    print(f"  monitors    : {len(sim.monitors)}")
    print(f"  T-rail period P_T = {P_T} μm  (segmented length = {LTL} μm)")
    print(f"  CPW span W_CPW    = {W_CPW} μm  (gap inc. T-rails GW = {GW} μm)")
