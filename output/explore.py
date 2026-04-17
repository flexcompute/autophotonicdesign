"""Mode-solver exploration: compute n_eff(W) for TE0 and TE2 of a silicon slab
waveguide, to design an adiabaticity-matched taper profile.
"""

import numpy as np
import tidy3d as td
from tidy3d.plugins.mode import ModeSolver

WAVELENGTH = 1.55
FREQUENCY = td.C_0 / WAVELENGTH
WG_HEIGHT = 0.22

Si = td.Medium.from_nk(n=3.47, k=0, freq=FREQUENCY)
SiO2 = td.Medium.from_nk(n=1.44, k=0, freq=FREQUENCY)

widths = np.linspace(0.5, 5.0, 19)  # 19 widths from 0.5 to 5.0
results = []

for W in widths:
    box_size = (0, max(W + 3, 4.0), 2.0)
    # Build a cross-section simulation
    structure = td.Structure(
        geometry=td.Box.from_bounds(
            rmin=(-td.inf, -W / 2, -WG_HEIGHT / 2),
            rmax=(td.inf, W / 2, WG_HEIGHT / 2),
        ),
        medium=Si,
    )
    sim = td.Simulation(
        size=(0.5, box_size[1], box_size[2]),
        structures=[structure],
        sources=[],
        monitors=[],
        run_time=1e-12,
        medium=SiO2,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=WAVELENGTH),
        boundary_spec=td.BoundarySpec.all_sides(boundary=td.PML()),
    )
    plane = td.Box(center=(0, 0, 0), size=(0, box_size[1], box_size[2]))
    mode_spec = td.ModeSpec(num_modes=6, target_neff=3.3, filter_pol="te")
    ms = ModeSolver(simulation=sim, plane=plane, mode_spec=mode_spec, freqs=[FREQUENCY])
    mode_data = ms.solve()
    n_effs = mode_data.n_eff.values[0]  # shape (num_modes,)
    # We only care about even TE modes (TE0, TE2, TE4...).
    # Symmetry: ModeSolver doesn't filter by parity, we'll take 0,2,4 indices.
    # Actually with filter_pol='te', it sorts by neff. The order is TE0>TE1>TE2>...
    results.append([W] + list(n_effs))
    print(f"W={W:.3f} um : n_eff = {n_effs}")

arr = np.array(results)
np.save("output/neff_vs_W.npy", arr)
print("\nSaved output/neff_vs_W.npy")
print("columns: W, n_eff[0..5]")
