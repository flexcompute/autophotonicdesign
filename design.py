"""design.py — PN junction design file.  THE AGENT MODIFIES THIS FILE.

Current device: Silicon lateral PN phase shifter (SISCAP-style constant doping).
Platform     : cSi on SiO₂, 220 nm Si, 90 nm slab, 1.31 µm O-band.
Metric       : FOM = -VπL_dB - λ_C·C_norm - λ_α·α_norm  (higher = better).

The agent may only edit:
    - IMPLANTS           (list[DopingRegion])
    - W_CORE             (rib width, µm, bounded [0.40, 0.70])
    - V_SWEEP            (reverse-bias points, V)

Keep create_simulation() and evaluate() structurally unchanged — they are
the harness for simulate.py. If the agent wants to use a non-constant
topology (U / L / V / graded), it should re-compose IMPLANTS by calling
`tools.doping_builders.build_*` helpers instead of rewriting create_simulation.
"""
from __future__ import annotations

from tools.doping_builders import DopingRegion, build_lateral_pn


# =========================================================================
# Device / platform constants  (FIXED — do not edit)
# =========================================================================
WAVELENGTH_UM = 1.31
H_CORE        = 0.220         # silicon rib height  (µm)
H_SLAB        = 0.090         # slab thickness      (µm)
W_CLEARANCE   = 2.000         # slab half-extent outside the rib
W_CONTACT     = 1.000         # contact / side-pad width per side
OXIDE_TOP     = 1.200         # TOX above slab
BOX_THICK     = 2.000         # BOX below slab
# Convention: P contact grounded at 0 V, N contact swept over V_SWEEP.
# Positive V on the N contact = reverse bias on this PN junction.
TARGET_BIAS_V = +1.0          # reverse-bias magnitude at which V\u03c0L / C are reported


# =========================================================================
# Agent-editable knobs
# =========================================================================
W_CORE = 0.500                # rib width (µm), allowed [0.40, 0.70]

# All reverse-bias (positive on N contact, P grounded).
V_SWEEP: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0)

# Constant-doping baseline (matches SISCAP TWModulator_Simple_latest.ipynb).
# To switch topologies the agent replaces this list — e.g.:
#
#   from tools.doping_builders import build_ushape_pn   # later when added
#   IMPLANTS = build_ushape_pn(...)
#
IMPLANTS: list[DopingRegion] = build_lateral_pn(
    Np_core=5e17, Nn_core=3e17,
    Np_plus=2e18, Nn_plus=3e18,
    Np_pp=1e20,   Nn_pp=1e20,
    y_junction=0.0,
    wp_plus=0.12, wn_plus=0.14,
    h_core=H_CORE, h_slab=H_SLAB, w_core=W_CORE,
    w_clearance=W_CLEARANCE, w_contact=W_CONTACT,
)


# =========================================================================
# Shared geometry dict — re-used by preview.py, drc.py, simulate.py
# =========================================================================
def geometry() -> dict:
    return dict(
        h_core=H_CORE, h_slab=H_SLAB, w_core=W_CORE,
        w_clearance=W_CLEARANCE, w_contact=W_CONTACT,
    )


# =========================================================================
# create_simulation — builds the Tidy3D CHARGE simulation from IMPLANTS.
# (Kept skeletal here on purpose: simulate.py is the actual driver.)
# =========================================================================
def create_simulation():
    """Return (charge_sim, handles) with the current IMPLANTS wired in.

    Imports Tidy3D lazily so that preview.py / drc.py can import this
    module without needing a working tidy3d install for pure-geometry
    inspection.
    """
    from tools.charge_sim import build_charge_simulation    # local import
    return build_charge_simulation(
        implants=IMPLANTS,
        geometry=geometry(),
        v_sweep=V_SWEEP,
        wavelength_um=WAVELENGTH_UM,
    )


def evaluate(sim_data, mode_results=None):
    """Compute the FOM from CHARGE + (optionally) mode-solver results.

    Parameters
    ----------
    sim_data       : HeatChargeSimulationData
    mode_results   : dict {"V": ndarray, "neff": ndarray complex} or None

    Returns
    -------
    dict with keys {FOM, VpiL_Vcm, C_pF_mm, loss_dB_cm}. simulate.py
    prints these as `metric: ...` so the agent can grep them out of the
    run log.
    """
    from tools.fom import compute_fom
    return compute_fom(sim_data, mode_results, target_bias_v=TARGET_BIAS_V,
                       wavelength_um=WAVELENGTH_UM)


def snapshot_header() -> str:
    return (
        f"# W_CORE={W_CORE}  H_CORE={H_CORE}  H_SLAB={H_SLAB}\n"
        f"# V_SWEEP={V_SWEEP}  TARGET_BIAS_V={TARGET_BIAS_V}\n"
        f"# n_regions={len(IMPLANTS)}"
    )
