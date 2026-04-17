# Silicon Photonic Waveguide Crossing — Design Showcase

> This branch showcases a single run of the auto-design agent on a compact
> silicon-photonic broadband waveguide crossing. **See the
> [main branch](../../tree/main) for the project introduction, setup, and
> full description of the framework.**

The agent was given a simple linear dual-taper baseline and asked to
maximize mean mode transmission (west → east) over 1.5–1.6 µm within a
6 × 6 µm design region, with 150 nm minimum feature size and the
device-level symmetry x ↔ −x, y ↔ −y. Over 50 experiments it iterated
through taper profiles, MMI parameters, and arm topology — eventually
discovering that because the x ↔ −x / y ↔ −y symmetry does *not* require
the horizontal and vertical arms to be identical, it could optimize
asymmetrically for the W → E metric.

## Final Result

**98.96 % mean transmission ≈ −0.045 dB insertion loss** across 1.5–1.6 µm.

### Geometry

![preview](output/preview.png)

Two orthogonal arms, independently parametrized, intersecting at the origin:

| Arm | Feed (µm) | Taper profile | MMI flat half-length | MMI width |
|---|---|---|---|---|
| Horizontal (W ↔ E) | 500 nm → 1.30 µm | Parabolic (t²) | 1.60 µm (3.20 µm flat) | 1.30 µm |
| Vertical (N ↔ S) | 500 nm → 0.80 µm | Parabolic (t²) | 1.70 µm (3.40 µm flat) | 0.80 µm |

The horizontal arm forms an MMI that self-images the input mode across
3.2 µm of flat multimode section between two 1.4 µm parabolic tapers.
The vertical arm is deliberately kept narrow (0.80 µm vs the H-arm's
1.30 µm) so it passes through the horizontal MMI with minimal
perturbation, while still providing a functional connection between the
north and south feed waveguides.

### Field Distribution

![field](output/field.png)

Clean single-image propagation through the horizontal MMI, almost no
sideways scatter into the perpendicular arms, and low-ripple
transmission into the east output.

## Optimization Progress

![progress](output/progress.png)

The trajectory runs through four phases:

- **Exp 1–6 (0.81 → 0.87):** baseline linear dual-taper, then smooth
  parabolic profile, then width sweep (peak at 1.4 µm).
- **Exp 7–10 (0.87 → 0.93):** topology change to MMI with a flat
  central section — large jump from self-imaging over a constant-width
  region.
- **Exp 11–35 (0.93 → 0.97):** parameter refinement and taper-profile
  studies (linear / cubic / exponential / cosine — all worse than
  parabolic), edge fillets (discarded), and 2D (width, length) sweep
  of the symmetric MMI.
- **Exp 36–50 (0.97 → 0.99):** **breakthrough** — breaking H/V arm
  symmetry after realizing the problem's mirror symmetries don't
  require diagonal symmetry. Narrow V arm + wide H arm gives the
  horizontal mode an almost-transparent pass-through.

Full reasoning and discarded experiments are in
[output/journal.md](output/journal.md); raw metrics in
[output/results.tsv](output/results.tsv).

## Files of Interest

- [design.py](design.py) — final device geometry
- [output/best_design.py](output/best_design.py) — snapshot of the best design
- [output/journal.md](output/journal.md) — experiment-by-experiment reasoning
- [output/results.tsv](output/results.tsv) — raw metrics log
- [output/preview.png](output/preview.png), [output/field.png](output/field.png), [output/progress.png](output/progress.png)
