# Silicon Photonic Waveguide Taper — Design Showcase

> This branch showcases a single run of the auto-design agent on a compact
> silicon-photonic waveguide taper. **See the [main branch](../../tree/main)
> for the project introduction, setup, and full description of the framework.**

The agent was given a blank slate (a trivial linear-taper baseline) and asked
to maximize fundamental-mode transmission at 1550 nm over a fixed 6 µm length,
expanding the mode 10× from a 0.5 µm single-mode waveguide to a 5 µm
multi-mode waveguide, with a 150 nm minimum feature size. Over 32 experiments
it iterated through parametric families, switched to gradient-based adjoint
optimization, and progressively scaled the control-point resolution.

## Final Result

**97.41 % fundamental-mode transmission ≈ −0.114 dB insertion loss** at 1550 nm.
A 15× reduction in loss vs. the linear-taper baseline (39.3% → 2.6%).

### Geometry

![preview](output/preview.png)

Layout (x ∈ [0, 6] µm):

| Section | x-range (µm) | Description |
|---|---|---|
| Narrow segment | 0.00 – 5.90 | Monotonic free-form sidewall, 500 nm → 3.84 µm |
| Step segment | 5.90 – 6.00 | Short aggressive widening, 3.84 µm → 5.00 µm |

The narrow segment is a concave-up profile that starts fast at the input
(where TE0–TE2 β-separation is large) and slows down approaching mid-taper.
The 100 nm step segment exploits the near-degeneracy of wide TE0 modes —
at W = 3.84 µm vs 5 µm the fundamental-mode profiles are nearly identical,
so an abrupt widening there has ≥ 0.99 projection overlap and costs
essentially no loss. Both segments are defined by **162 control widths
optimized jointly via Tidy3D adjoint FDTD** (120 narrow + 40 step + 2
endpoints).

### Field Distribution

![field](output/field.png)

Smooth fundamental-mode expansion across the taper with no visible
scattering into higher-order even modes or radiation into the cladding.

## Optimization Progress

![progress](output/progress.png)

The jump from T ≈ 0.64 to 0.92 at experiment 5 is the "sqrt-narrow + wide-end
step" discovery. Experiments 6–32 are gradient-based refinements via
Tidy3D autograd, with parameter count scaled 8 → 10 → 16 → 24 → 37 → 66 →
106 → 161 at warm-started checkpoints.

Full reasoning and discarded experiments are in
[output/journal.md](output/journal.md); raw metrics in
[output/results.tsv](output/results.tsv).

## Files of Interest

- [design.py](design.py) — final device geometry
- [output/best_design.py](output/best_design.py) — snapshot of the best design
- [output/journal.md](output/journal.md) — experiment-by-experiment reasoning
- [output/results.tsv](output/results.tsv) — raw metrics log
- [output/preview.png](output/preview.png), [output/field.png](output/field.png), [output/progress.png](output/progress.png)
