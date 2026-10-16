# Agent Team: Design a Whole Photonic Chip

A team of AI agents (Claude Code subagents) designs a complete photonic chip from a spec: system
design, components, layout and routing, DRC and LVS, post-layout circuit simulation, and heater
calibration on virtual dies. A lead agent plans and gates the work; four specialists do it.

The demo chip is a two-channel heated MZI lattice demux on SiPhoPDK (O-band): flat-top pass bands
at 1310 nm and 1315 nm, heaters that set the lattice phases and correct die-to-die variation.

## Difference from `main`

`main` and the device branches run **one agent on one device**: edit `design.py`, run FDTD, keep or
discard. This branch runs **a team on a whole chip**, so the harness changes:

| | `main` | `agent_team` |
|---|---|---|
| Agents | one | lead + architect, component, layout, judge (`.claude/agents/`) |
| Unit of work | one device geometry | a chip: system, blocks, layout, calibration |
| Shared memory | `journal.md`, `principles.md` | blackboard `team/`: targets, achieved, reviews, journal, lessons |
| Pass/fail | one metric from FDTD | gates in `tools/verify.py`: build, DRC, LVS, nominal post-layout performance, blind virtual dies |
| Simulation | Tidy3D FDTD in the cloud | PhotonForge circuit simulation, offline and free (FDTD only for a part with no model) |
| Grading | the agent scores itself | an independent judge agent and frozen tools; calibration is tested on dies nobody has seen |

## How it works

```
spec.md + spec.yaml  (the human)
        |
   lead (program.md) ---- plan, brief, gate, report
        |
   P1 architect   -> targets per block          gate A: judge re-runs the system sim
   P2 component   -> achieved per block         gate B: judge re-checks each block
   P3 layout      -> design/chip.py             gate C: verify build, DRC, LVS
   P4 architect   -> phase trims + tuning.py    verify nominal + training dies
   P5 judge       -> full verify, 8 blind dies  final: verify ALL PASS + review PASS
   P6 lead        -> output/REPORT.md
```

**Why a judge and blind dies.** "DRC clean, LVS clean, the simulation runs" does not mean the chip
works: our first reference lattice passed all three and was not a filter. The judge scores the
response shape against the spec, reads the plots and the code, and the calibration routine runs on
new random dies at every final check, so it cannot be tuned to the dies it has seen.

**The virtual test station** (`tools/measure.py`) acts like a prober. Each die has an n_eff error on
every waveguide piece (offset, gradient, local noise) and an error on every coupler, from the sigmas
in `spec.yaml`. `calibrate(station)` sets heaters and reads noisy spectra, with a budget of 60
measurements per die.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install "photonforge>=2.0" tidy3d-extras pyyaml scipy matplotlib
pip install siphopdk-forge            # SiPhoPDK (internal wheel for now)
claude "Follow the instructions in program.md and design the chip in spec.md"
```

Watch it: `python tools/team.py status` (the board), `output/verify.png` (the latest check),
`tools/view.py` (the layout in the LiveViewer).

## Use it for another chip

The harness does not know about lattices. A new chip needs only:

1. `spec.md` and `spec.yaml`: function, ports, targets (metrics from `tools/metrics.py`), variation.
2. A metric in `tools/metrics.py` if the spec needs one that is not there.
3. A PDK adapter `tools/pdks/<pdk>.py` (technology, cells, DRC, LVS, fast route models) for a new PDK.

It fits passive and thermally tuned circuits with PDK models: ring filters, switch meshes, splitter
trees, transceiver passives. Not yet: electro-optic modulators (charge and RF simulations), eye-diagram
specs (a time-domain metric), and parts with no model (FDTD per part: FlexCredits and time).

## Project structure

| Path | Role |
|---|---|
| `program.md` | the lead's instructions: phases, gates, rules |
| `spec.md`, `spec.yaml` | what to build (words, numbers); only the human edits them |
| `.claude/agents/` | `architect`, `component`, `layout`, `judge` |
| `design/chip.py` | `build() -> pf.Component` (layout agent) |
| `design/tuning.py` | `calibrate(station)` (architect) |
| `design/components/` | new PCells, only when no PDK cell fits |
| `team/` | blackboard: `plan.md`, `principles.md`, `targets/`, `achieved/`, `reviews/`, `journal.jsonl`, `LESSONS.md` |
| `tools/verify.py` | the gates; writes `output/verify.json` and `output/verify.png` |
| `tools/measure.py` | virtual test station (dies, heaters, noisy spectra) |
| `tools/metrics.py` | metric library (channel, insertion loss, imbalance) |
| `tools/routing.py` | LVS-safe optical routing (`route_auto` split per net) |
| `tools/team.py` | journal, status board, cloud spend |
| `tools/pdks/siphopdk.py` | PDK adapter |
| `tools/noclouds.py` | blocks cloud runs inside the checks |
