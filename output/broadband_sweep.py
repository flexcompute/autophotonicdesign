from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import tidy3d as td
import tidy3d.web as web

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import (
    BUFFER,
    FREQUENCY,
    MFD,
    TAPER_LENGTH,
    WG_HEIGHT,
    WG_WIDTH,
    WAVELENGTH,
    create_simulation,
)


OUT_DIR = Path("output")
DATA_PATH = OUT_DIR / "sim_data" / "broadband_optimal.hdf5"
TSV_PATH = OUT_DIR / "broadband_insertion_loss.tsv"
PNG_PATH = OUT_DIR / "broadband_insertion_loss.png"


def main():
    wavelengths = np.linspace(1.26, 1.36, 41)
    freqs = td.C_0 / wavelengths

    sim = create_simulation()

    broadband_source = td.GaussianBeam(
        center=(-BUFFER / 2, 0, 0),
        size=(0, td.inf, td.inf),
        source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY / 10),
        direction="+",
        waist_radius=MFD / 2,
        waist_distance=0.0,
        pol_angle=0.0,
        name="gaussian_in_broadband",
    )

    broadband_monitor = td.ModeMonitor(
        center=(TAPER_LENGTH + BUFFER / 2, 0, 0),
        size=(0, 4 * WG_WIDTH, 4 * WG_HEIGHT + 2.0),
        freqs=freqs,
        mode_spec=td.ModeSpec(num_modes=1, target_neff=1.72),
        name="mode",
    )

    sim = sim.updated_copy(
        sources=[broadband_source],
        monitors=[broadband_monitor],
        run_time=4e-12,
    )

    print("=== Broadband simulation ===")
    print(f"wavelength range: {wavelengths[0]:.3f} to {wavelengths[-1]:.3f} um")
    print(f"points: {len(wavelengths)}")
    print(f"sim size: {tuple(round(s, 2) for s in sim.size)} um")

    sim_data = web.run(
        sim,
        task_name="autodesign_broadband_optimal",
        path=str(DATA_PATH),
    )

    amps = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    transmission = np.abs(amps) ** 2
    insertion_db = 10 * np.log10(np.maximum(transmission, 1e-30))

    order = np.argsort(wavelengths)
    wavelengths = wavelengths[order]
    transmission = transmission[order]
    insertion_db = insertion_db[order]

    rows = ["wavelength_um\tT\t10log10_T_dB"]
    for wl, t, db in zip(wavelengths, transmission, insertion_db):
        rows.append(f"{wl:.6f}\t{t:.12g}\t{db:.9f}")
    TSV_PATH.write_text("\n".join(rows) + "\n", encoding="utf-8")

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(wavelengths, insertion_db, marker="o", linewidth=1.8, markersize=3.5)
    ax.set_xlabel("Wavelength (um)")
    ax.set_ylabel("10 log10(T) (dB)")
    ax.set_title("Optimized Edge Coupler Broadband Response")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(wavelengths[0], wavelengths[-1])
    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=180)
    plt.close(fig)

    print(f"Saved {TSV_PATH}")
    print(f"Saved {PNG_PATH}")
    print("=== Summary ===")
    print(f"best_dB: {float(np.max(insertion_db)):.6f}")
    print(f"worst_dB: {float(np.min(insertion_db)):.6f}")
    print(f"mean_dB: {float(np.mean(insertion_db)):.6f}")
    idx_1310 = int(np.argmin(np.abs(wavelengths - WAVELENGTH)))
    print(f"dB_at_1p31um: {float(insertion_db[idx_1310]):.6f}")


if __name__ == "__main__":
    main()
