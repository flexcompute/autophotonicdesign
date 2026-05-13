"""modesolve.py — Perturbed mode solve on the CHARGE carrier data.

For each bias in the sweep we:
  1. pull electron / hole densities out of the SteadyFreeCarrierMonitor;
  2. build a `PerturbationMedium` off the Nedeljkovic–Soref–Mashanovich
     plasma-dispersion model (standard for O-band silicon);
  3. run a 2D mode solve on the rib cross-section (single fundamental TE).

Returns a dict {"V": ndarray, "neff": ndarray complex, "E_abs_map": ..., ...}
that `tools.fom.compute_fom` turns into VπL(V) and loss(V).

The mode solves are submitted as a single `web.Batch`, same as the SISCAP
notebook.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np


def run_mode_solver_batch(
    charge_sim_data,
    implants,
    geometry: dict,
    v_sweep: Sequence[float],
    wavelength_um: float = 1.31,
    path_dir: str = "output/mode_batch",
    mesh_refinement: int = 40,
) -> dict:
    """Run per-bias mode solves, return {V, neff, ...}.

    `charge_sim_data` : HeatChargeSimulationData returned by web.run.
    """
    import tidy3d as td
    from tidy3d import web

    freq0 = td.C_0 / wavelength_um

    # --- Materials (same recipe as SISCAP) ----------------------------
    si = td.material_library["cSi"]["Palik_Lossless"]
    n_si, k_si = si.nk_model(frequency=freq0)
    si_non_perturb = td.Medium.from_nk(n=float(n_si), k=float(k_si), freq=freq0)

    pert_model = td.NedeljkovicSorefMashanovich(ref_freq=freq0)
    si_perturb = td.PerturbationMedium.from_unperturbed(
        medium=si_non_perturb,
        perturbation_spec=td.IndexPerturbation(
            delta_n=pert_model.delta_n(),
            delta_k=pert_model.delta_k(),
            freq=freq0,
        ),
    )
    SiO2 = td.Medium.from_nk(n=1.447, k=0.0, freq=freq0)

    # --- Carrier monitor -> per-V SpatialDataArrays -------------------
    carriers = charge_sim_data["carriers"]

    # --- Build one ModeSolver per bias --------------------------------
    mode_sims = {}
    keys = []
    for v in v_sweep:
        e_data = carriers.electrons.sel(voltage=float(v))
        h_data = carriers.holes.sel(voltage=float(v))
        si_perturb_v = si_perturb.perturbed_copy(
            electron_density=e_data, hole_density=h_data
        )

        h_core = geometry["h_core"]; h_slab = geometry["h_slab"]
        w_core = geometry["w_core"]
        # Minimal 2D mode-solver simulation: oxide + doped-Si rib + slab.
        oxide = td.Structure(
            geometry=td.Box(center=(0, 0, 0),
                            size=(td.inf, td.inf, 5.0)),
            medium=SiO2, name="oxide",
        )
        core = td.Structure(
            geometry=td.Box(center=(0, 0, h_core / 2),
                            size=(td.inf, w_core, h_core)),
            medium=si_perturb_v, name="core",
        )
        slab = td.Structure(
            geometry=td.Box(center=(0, 0, h_slab / 2),
                            size=(td.inf, 4.0, h_slab)),
            medium=si_perturb_v, name="slab",
        )

        ms_sim = td.Simulation(
            size=(0, 3.0, 2.0),
            center=(0, 0, h_core / 2),
            structures=[oxide, core, slab],
            medium=SiO2,
            run_time=1e-15,                     # placeholder, mode solver ignores
            grid_spec=td.GridSpec.auto(
                min_steps_per_wvl=mesh_refinement,
                wavelength=wavelength_um,
            ),
            boundary_spec=td.BoundarySpec.all_sides(boundary=td.PML()),
        )
        mode_plane = td.Box(center=(0, 0, h_core / 2), size=(0, 3.0, 2.0))
        from tidy3d.plugins.mode import ModeSolver
        ms = ModeSolver(
            simulation=ms_sim,
            plane=mode_plane,
            mode_spec=td.ModeSpec(num_modes=1, target_neff=2.8),
            freqs=[freq0],
        )
        key = f"V_{v:+.3f}"
        mode_sims[key] = ms
        keys.append((key, v))

    # --- Batch submit -------------------------------------------------
    batch = web.Batch(simulations=mode_sims, verbose=True)
    batch_results = batch.run(path_dir=path_dir)

    # --- Collect neff(V) ---------------------------------------------
    V = np.array([v for _, v in keys])
    neff = np.zeros(len(keys), dtype=complex)
    for i, (key, _) in enumerate(keys):
        data = batch_results[key]
        neff[i] = complex(data.n_complex.isel(mode_index=0).item())

    # Real part -> phase shift, imag part -> loss
    delta_neff = neff.real - neff.real[np.argmin(np.abs(V - 0.0))]
    dphi_per_L_rad_cm = 2 * np.pi * delta_neff / wavelength_um * 1e4  # rad/cm
    # dφ/dV (rad/cm/V)
    dphidL_dv = np.gradient(dphi_per_L_rad_cm, V)
    with np.errstate(divide="ignore", invalid="ignore"):
        VpiL = np.pi / dphidL_dv                                     # V·cm
    loss_dB_cm = (
        10 * 4 * np.pi * neff.imag / wavelength_um * 1e4 * np.log10(np.e)
    )

    return dict(
        V=V, neff=neff, delta_neff=delta_neff,
        VpiL_Vcm=VpiL, loss_dB_cm=loss_dB_cm,
    )
