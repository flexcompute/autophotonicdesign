# team/: shared files

The agents share their work only through the files in this folder. Each file has one owner.

| Path | Owner | Content |
|---|---|---|
| `plan.md` | lead | ASCII block diagram, owner of each block, phases |
| `principles.md` | architect | theory and references for this chip type (one page) |
| `targets/<block>.json` | architect | the target of each block |
| `achieved/<block>.json` | component | the achieved value of each block, with evidence |
| `reviews/<gate>.md` | judge | the decision for each gate: `gateA.md`, `gateB.md`, `gateC.md`, `final.md` |
| `work/<agent>/` | that agent | scripts, sweeps, plots |
| `journal.jsonl` | all agents, with `tools/team.py log` | one line for each decision or result |
| `LESSONS.md` | all agents (add at the end only) | tool problems, PDK data, and their solutions |

## Format of `targets/<block>.json`

```json
{"block": "coupler_1", "owner": "component",
 "target": {"power_coupling": {"value": 0.50, "tol": 0.02}, "loss_db": {"max": 0.2}},
 "band_um": [1.300, 1.320],
 "why": "first coupler of the lattice; the isolation decreases by 1 dB for each 0.03 of error"}
```

## Format of `achieved/<block>.json`

```json
{"block": "coupler_1", "cell": "library.directional_coupler",
 "params": {"coupling_length": 15.0},
 "achieved": {"power_coupling": 0.489, "loss_db": 0.1},
 "meets_target": true, "margin": "0.011 of 0.02",
 "binding_constraint": "the PDK model sets the loss to 0.1 dB",
 "evidence": "team/work/component/coupler_1.png"}
```

## Format of `reviews/<gate>.md`

1. The first line is `PASS` or `FIX`.
2. A numbered list of problems. Each problem gives: the location (file and line, or the plot), the
   problem, the evidence, the owner, and the correction.
3. What is good.
