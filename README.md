# AutoPhotonicDesign · PN-Modulator Branch

An autonomous design agent for a silicon lateral PN phase shifter, built on
the same loop as [`main`](https://github.com/flexcompute/autophotonicdesign)
but with a multiphysics simulator (CHARGE + per-bias mode solve) and a
joint figure-of-merit over modulation efficiency, junction capacitance, and
propagation loss.

## What it does

The agent edits `design.py` to vary the implant geometry, doping levels, and
rib width of a SiSCAP-style lateral PN modulator at 1.31 µm. Each iteration
runs a drift-diffusion CHARGE simulation across a five-point bias sweep
(0 to 2 V reverse), feeds the carrier density into a per-bias mode solver,
and computes:

- `VπL_Vcm` — modulation efficiency (lower is better)
- `C_pF_mm` — small-signal junction capacitance
- `loss_dB_cm` — optical propagation loss at the target bias
- `FOM` — scalar combiner (higher is better)

The agent keeps a journal of every experiment (hypothesis, result, lesson)
and after ~30 iterations across topology families (lateral, U-shape, L-shape,
graded) it converges to a design on the published VπL · C envelope.

## Layout

```
.
├── program.md            # Agent brief: device, constraints, loop rules
├── design.py             # THE ONLY FILE THE AGENT MODIFIES
├── simulate.py           # CHARGE + mode-solver batch + auto-archives the run
├── preview.py            # 2D doping cross-section, free
├── drc.py                # Implant geometry / physics rules
├── schematic.svg         # Loop diagram
├── tools/                # Load-bearing harness modules
│   ├── doping_builders.py    # build_lateral_pn, build_ushape_pn, build_graded, …
│   ├── charge_sim.py         # Tidy3D CHARGE simulation builder
│   ├── modesolve.py          # Per-bias mode solver
│   ├── fom.py                # Scalar figure-of-merit
│   ├── journal.py            # output/journal.md + results.tsv manager
│   ├── viz.py                # Doping / carrier visualizations
│   ├── evolution.py          # Iteration GIF builder
│   ├── dashboard.py          # output/dashboard.html builder
│   └── literature_data.py    # Published VπL · C envelope for context
├── output/               # Auto-generated; .gitignored
└── README.md
```

## Difference from the main (passive) template

This branch does **not** use `orchestrate.py`. The PN flow has more
bookkeeping baked into `simulate.py` (CHARGE archiving, mode-batch result
caching, dashboard re-generation) so the agent doesn't need an external
keep/discard driver. The contract is otherwise identical: agent edits
`design.py` and re-runs `simulate.py`; `tools/journal.py` handles the rest.

## Quickstart

```bash
# 1. Install dependencies (Python 3.10+)
pip install tidy3d klayout numpy matplotlib

# 2. Configure Tidy3D (one-time)
tidy3d configure --apikey=<your-key>

# 3. Verify the geometry renders cleanly (no cloud spend)
python preview.py
python drc.py

# 4. Run one full experiment (≈2 min, ≈0.02 FlexCredit)
python simulate.py --description "constant baseline"

# 5. Hand off to the agent
claude "Follow the instructions in program.md and start designing!"
```

## Iter-1 baseline

`design.py` ships with the SiSCAP-style constant-doping baseline from
Yong 2017. On the GPU cloud you should reproduce FOM ≈ 2.74e-05,
VπL ≈ 1.82 V·cm, C ≈ 0.26 pF/mm, α ≈ 10.6 dB/cm at +1 V reverse bias.
That's the starting point. The agent moves from there.

## Citation

If you use this in published work, please cite Flexcompute's
[Agentic Photonic Design for Modulators](https://hs.flexcompute.com/blog/agentic-photonic-design-modulators)
blog post.
