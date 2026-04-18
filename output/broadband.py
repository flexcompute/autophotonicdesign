"""Broadband insertion-loss sweep of the best design.

Rebuilds the simulation from output/best_design.py but replaces the source
and monitor with a broadband pulse and 31-point mode monitor spanning
1.5 µm - 1.6 µm.  Saves output/broadband_IL.png.
"""
import importlib.util
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import tidy3d as td
import tidy3d.web as web


def _load_best_design():
    """Import output/best_design.py as a module named `best_design`."""
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "best_design", here / "best_design.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["best_design"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    bd = _load_best_design()
    sim = bd.create_simulation()

    wavelengths = np.linspace(1.5, 1.6, 31)
    freqs = td.C_0 / wavelengths
    f0 = bd.FREQUENCY
    fwidth = f0 / 8          # broadband pulse covering ~1.4-1.7 µm

    bb_source = td.ModeSource(
        center=bd.source.center,
        size=bd.source.size,
        source_time=td.GaussianPulse(freq0=f0, fwidth=fwidth),
        direction="+",
        mode_spec=bd.source.mode_spec,
        mode_index=0,
        name="input_mode",
    )

    bb_monitor = td.ModeMonitor(
        center=bd.mode_monitor.center,
        size=bd.mode_monitor.size,
        freqs=list(freqs),
        mode_spec=bd.mode_monitor.mode_spec,
        name="mode",
    )

    field_monitor = td.FieldMonitor(
        size=(td.inf, td.inf, 0),
        freqs=[f0],
        name="field_xy",
    )

    sim_bb = sim.updated_copy(
        sources=[bb_source],
        monitors=[bb_monitor, field_monitor],
        run_time=6e-12,      # broadband pulse needs longer run to decay
    )

    print(f"=== Submitting broadband sim ({len(freqs)} points, "
          f"{wavelengths.min()*1e3:.0f}-{wavelengths.max()*1e3:.0f} nm) ===")
    sim_data = web.run(
        sim_bb, task_name="broadband_IL",
        path="output/sim_data/broadband.hdf5",
    )

    amps = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = np.abs(amps) ** 2
    IL_dB = -10.0 * np.log10(np.clip(T, 1e-12, None))

    print(f"{'wl (nm)':>8}  {'T':>7}  {'IL (dB)':>8}")
    for wl, t, il in zip(wavelengths, T, IL_dB):
        print(f"{wl*1e3:8.1f}  {t:7.4f}  {il:8.4f}")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(wavelengths * 1e3, IL_dB, "-", color="darkgreen", linewidth=2)
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Insertion loss (dB)")
    ax.grid(True, alpha=0.3)
    ax.set_title("Broadband insertion loss — best design")

    # Inset: |E| field at 1550 nm (manual plot to avoid auto-colorbar overlap)
    fd = sim_data["field_xy"]
    # colocate=True default: Ex, Ey, Ez share the same grid
    Ex = fd.Ex.squeeze().values
    Ey = fd.Ey.squeeze().values
    Ez = fd.Ez.squeeze().values
    E_abs = np.sqrt(np.abs(Ex) ** 2 + np.abs(Ey) ** 2 + np.abs(Ez) ** 2).T
    x = fd.Ex.x.values
    y = fd.Ex.y.values
    # pcolormesh uses cell-edge coordinates, so expand to cell edges
    x_edges = np.concatenate(([x[0] - 0.5 * (x[1] - x[0])],
                              0.5 * (x[:-1] + x[1:]),
                              [x[-1] + 0.5 * (x[-1] - x[-2])]))
    y_edges = np.concatenate(([y[0] - 0.5 * (y[1] - y[0])],
                              0.5 * (y[:-1] + y[1:]),
                              [y[-1] + 0.5 * (y[-1] - y[-2])]))

    inset = ax.inset_axes([-0.05, 0.35, 0.55, 0.55])
    inset.pcolormesh(x_edges, y_edges, E_abs, cmap="inferno", shading="flat")

    # Overlay bend geometry boundaries
    for structure in sim_bb.structures:
        geom = structure.geometry
        if isinstance(geom, td.PolySlab):
            verts = np.array(geom.vertices)
            verts_closed = np.vstack([verts, verts[0]])
            inset.plot(verts_closed[:, 0], verts_closed[:, 1],
                       color="white", linewidth=0.7, alpha=0.9)
        elif isinstance(geom, td.Box):
            (xmin, ymin, _), (xmax, ymax, _) = geom.bounds
            xmin = max(xmin, x.min())
            ymin = max(ymin, y.min())
            xmax = min(xmax, x.max())
            ymax = min(ymax, y.max())
            inset.plot([xmin, xmax, xmax, xmin, xmin],
                       [ymin, ymin, ymax, ymax, ymin],
                       color="white", linewidth=0.7, alpha=0.9)

    inset.set_xlim(x_edges[0], x_edges[-1])
    inset.set_ylim(y_edges[0], y_edges[-1])
    inset.set_aspect("equal")
    inset.set_title("|E| at 1550 nm", fontsize=9)
    inset.set_xlabel("x (µm)", fontsize=8)
    inset.set_ylabel("y (µm)", fontsize=8)
    inset.tick_params(labelsize=7)

    fig.tight_layout()
    plt.savefig("output/broadband_IL.png", dpi=150, bbox_inches="tight")
    print("Saved output/broadband_IL.png")

    # Save raw data for reference
    np.savetxt(
        "output/broadband_IL.tsv",
        np.column_stack([wavelengths * 1e3, T, IL_dB]),
        header="wavelength_nm\tT\tIL_dB",
        delimiter="\t",
        comments="",
        fmt=["%.2f", "%.6f", "%.6f"],
    )
    print("Saved output/broadband_IL.tsv")


if __name__ == "__main__":
    main()
