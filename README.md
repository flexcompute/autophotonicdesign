# Photonic Device Auto-Design Agent

An autonomous photonic device design agent, inspired by Andrej Karpathy's
[autoresearch](https://github.com/karpathy/autoresearch). Instead of a human
manually tuning device geometry and running simulations, an LLM agent
(e.g. Claude Code) takes over the design loop: it reads instructions and
constraints from a Markdown file, modifies the device geometry in Python,
visually verifies the layout, runs a fabrication design-rule check, submits
FDTD simulations to Tidy3D's cloud solver, inspects the resulting field
patterns, and decides whether to keep or discard each design — all without
human intervention.

This repository holds the per-device design runs behind our paper on
autonomous agentic photonic design (manuscript in preparation); see
[Reproducing the paper](#reproducing-the-paper) below for the map from
branches to paper sections.

![schematic](schematic.svg)

## How It Works

Before the loop, the agent does a one-time **literature review** of the
target device class — common topologies, underlying physics, state-of-the-art
metrics — and captures it in `output/principles.md` as a stable design
reference.

Each iteration then runs through a fixed loop:

```
Explore → Design → Verify (DRC + preview) → Simulate → Log (keep/discard)
```

Long-term memory spans two files: `output/principles.md` holds the literature
review, and `output/journal.md` logs each experiment's hypothesis and lesson.
Together they let the agent learn from both successes and failures and avoid
repeating dead ends. The human's job is to define the problem (device type,
constraints, target metric) in `program.md`; the agent does the engineering.

## Reproducing the paper

`main` is the device-agnostic framework. Each demonstration in the paper was
run on its own branch; check out the branch to get that device's `program.md`,
`design.py`, run journal (`output/journal.md`), and best design.

| Branch | Paper § | Device | Headline result |
|--------|---------|--------|------------------|
| [`bend`](../../tree/bend) | 3.1 | SiN 90° bend, R = 12 µm | 0.109 dB (97.51% transmission) |
| [`1x2splitter`](../../tree/1x2splitter) | 3.1 | SOI 1×2 splitter | 0.015 dB insertion loss |
| [`taper`](../../tree/taper) | 3.1 | SOI taper, 6 µm | 0.114 dB |
| [`grating_coupler`](../../tree/grating_coupler) | 3.1 | SOI focused grating coupler | 2.89 dB peak coupling loss |
| [`crossing`](../../tree/crossing) | 3.1 | SOI waveguide crossing | 0.11 dB insertion loss |
| [`pn_modulator`](../../tree/pn_modulator) | 3.2 | Si microring modulator (lateral PN) | VπL·Cj ≈ 4.4 V·pF |
| [`rf_transmission_lines`](../../tree/rf_transmission_lines) | 3.3 | Segmented slow-wave CPW electrode | Z₀ ≈ 43–44 Ω; α₀ ≈ 0.29–0.36 (dB/cm/√GHz) |
| [`routing`](../../tree/routing) | 3.4 | Electrical routing, 32 nets | 192 → 0 DRC violations |

The [`edge_coupler`](../../tree/edge_coupler) branch is an additional device not reported in the paper.


## Project Structure

| File | Role |
|------|------|
| `program.md` | Agent instructions, constraints, loop rules |
| `design.py` | Device geometry (the only file the agent modifies) |
| `simulate.py` | Runs Tidy3D FDTD simulation, extracts metric, plots fields |
| `preview.py` | Generates geometry preview for visual inspection |
| `drc.py` | Fabrication rule check via KLayout |
| `orchestrate.py` | Post-simulation bookkeeping: parses run log, updates TSV/journal, handles keep/discard |
| `output/` | All generated files (principles, logs, plots, journal, best design) |

## Setup

Python 3.10+.

```bash
pip install tidy3d numpy matplotlib klayout
tidy3d configure --apikey=YOUR_API_KEY
```

Tidy3D is a paid cloud FDTD service; get an API key at
[tidy3d.simulation.cloud](https://tidy3d.simulation.cloud). The `routing` branch
additionally uses [PhotonForge](https://www.flexcompute.com/photonforge/) (a
Flexcompute product) for layout; the passive and active EM runs need only the
packages above.

## Running

Point Claude Code (or any compatible LLM agent with shell + Python
execution) at `program.md`:

```bash
claude "Follow the instructions in program.md and start designing!"
```

The agent will run the loop for the number of experiments specified in
`program.md` (default: 50). Watch progress in `output/journal.md` and
`output/results.tsv`.

## Customizing for a Different Device

To adapt this framework to a new photonic device:

1. Edit `program.md` — describe the target device, metric, and constraints.
2. Edit `design.py` — update the initial geometry and the `evaluate()`
   function that computes the target metric from simulation data.
3. The rest of the infrastructure (`simulate.py`, `preview.py`, `drc.py`,
   `orchestrate.py`) is device-agnostic and does not need to change.

## Credits

Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch).
Built on [Tidy3D](https://www.flexcompute.com/tidy3d/) for FDTD simulation
and [KLayout](https://www.klayout.de/) for DRC.
