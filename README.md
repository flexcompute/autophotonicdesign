# AutoPhotonicDesign · RF Transmission-Lines Branch

An autonomous design agent for an RF coplanar-waveguide (CPW) electrode
driving a thin-film lithium tantalate (LTOI300) Mach–Zehnder modulator.
Built on the same loop as [`main`](https://github.com/flexcompute/autophotonicdesign),
but the physics solver is Tidy3D's full-wave RF / `TerminalComponentModeler`
and the figure of merit is over three coupled microwave properties.

## What it does

The agent edits `design.py` to vary the T-rail geometry, CPW dimensions,
metal thickness, and dielectric stack of a segmented coplanar waveguide.
Each iteration submits a 3D Tidy3D RF simulation, extracts the S-matrix at
two wave ports, derives the transmission-line parameters from the S
parameters, and jointly drives:

- `α₀` — skin-effect-dominated microwave loss in dB/cm/√GHz (lower is better)
- `Re(Z₀)` — characteristic impedance toward 50 Ω
- `n_eff` — RF effective index toward 2.20 (matches TFLT TE optical group index at 1.31 µm)

After ~40 iterations across topology families (plain T-rail, asym-T,
wide-cap T, T+U, half-T) the agent maps the loss / impedance / index
frontier in about an hour of cloud time.

## Layout

```
.
├── program.md          # Agent brief: device, constraints, loop rules
├── design.py           # THE ONLY FILE THE AGENT MODIFIES
├── simulate.py         # 3D RF FDTD batch + S-matrix to (α, Z₀, n_eff) extractor
├── preview.py          # 2D top-down + cross-section, free
├── drc.py              # T-rail geometric / process rules
├── schematic.svg       # Loop diagram
├── tools/              # Load-bearing harness modules
│   ├── journal.py          # output/journal.md + results.tsv manager
│   ├── dashboard.py        # output/dashboard.html builder
│   ├── evolution.py        # Iteration GIF builder
│   └── build_blog.py       # Optional blog renderer
├── output/             # Auto-generated; .gitignored
└── README.md
```

## Difference from the main (passive) template

This branch does **not** use `orchestrate.py`. `simulate.py` self-manages
bookkeeping (auto-archives each experiment to `output/experiments/NNNN/`,
appends to `output/journal.md` / `output/results.tsv`, promotes best
designs, regenerates the dashboard). The agent contract is otherwise
identical: edit `design.py`, re-run `simulate.py`.

## Quickstart

```bash
# 1. Install dependencies (Python 3.10+)
pip install tidy3d klayout numpy matplotlib

# 2. Configure Tidy3D (one-time, RF-enabled account required)
tidy3d configure --apikey=<your-key>

# 3. Verify the geometry renders cleanly (no cloud spend)
python preview.py
python drc.py

# 4. Run one full experiment (≈12 min, ~$ in FlexCredit)
python simulate.py

# 5. Hand off to the agent
claude "Follow the instructions in program.md and start designing!"
```

## Iter-1 baseline

`design.py` ships with the plain T-rail CPW baseline. On the GPU cloud you
should reproduce: FOM ≈ −1.21, α₀ ≈ 0.66 dB/cm/√GHz, α @ 40 GHz ≈ 2.82 dB/cm,
Re(Z₀) @ 40 GHz ≈ 39.5 Ω, n_eff @ 40 GHz ≈ 2.02. The agent's job is to pull
Z₀ up to 50 Ω, n_eff up to 2.20, and α₀ down — without breaking the others.

## Citation

If you use this in published work, please cite Flexcompute's
[Agentic Photonic Design for RF Transmission Modulators](https://hs.flexcompute.com/blog/rf-transmission-modulators)
blog post.
