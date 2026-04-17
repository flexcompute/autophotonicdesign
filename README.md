# 1x2 Silicon Photonic Splitter — Design Showcase

> This branch showcases a single run of the auto-design agent on a compact
> silicon-photonic 1×2 power splitter. **See the [main branch](../../tree/main)
> for the project introduction, setup, and full description of the framework.**

The agent was given a blank slate (a trivial linear-Y baseline) and asked to
maximize total transmission at 1550 nm within a 4 × 10 µm footprint, with a
150 nm minimum feature size. Over 50 experiments it iterated on geometry
families, parameter choices, and grid resolution, ending at a compact MMI
splitter with an input mode-matching taper and cosine S-bend access arms.

## Final Result

**99.66 % total transmission ≈ −0.015 dB insertion loss** at 1550 nm.

### Geometry

![preview](output/preview.png)

Layout (x ∈ [0, 10] µm):

| Section | x-range (µm) | Description |
|---|---|---|
| Input taper | 0.00 – 1.50 | Linear taper, 500 nm → 950 nm |
| MMI body | 1.50 – 5.15 | Rectangular, 2.10 µm wide × 3.65 µm long |
| Access arms | 5.15 – 10.00 | Cosine-S-bent tapered polygons |

The arm polygons are shaped so the outer edge is flush with the MMI top
(no sub-150 nm DRC corner pockets) while the inner edge opens a 200 nm
center trench. Both edges are cosine-eased for adiabatic transition.

### Field Distribution

![field](output/field.png)

Clean two-lobe self-imaging inside the MMI, minimal scattering, and
low-ripple propagation down the two output waveguides.

## Optimization Progress

![progress](output/progress.png)

Full reasoning and discarded experiments are in
[output/journal.md](output/journal.md); raw metrics in
[output/results.tsv](output/results.tsv).

## Files of Interest

- [design.py](design.py) — final device geometry
- [output/best_design.py](output/best_design.py) — snapshot of the best design
- [output/journal.md](output/journal.md) — experiment-by-experiment reasoning
- [output/results.tsv](output/results.tsv) — raw metrics log
- [output/preview.png](output/preview.png), [output/field.png](output/field.png), [output/progress.png](output/progress.png)
