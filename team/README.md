# team/: the blackboard

Agents talk through files here, not through chat. Each file has one owner.

| Path | Owner | What |
|---|---|---|
| `plan.md` | lead | block diagram (ASCII), phases, owners, round count |
| `principles.md` | architect | short theory and literature notes for this chip type |
| `targets/<block>.json` | architect | what each block must achieve |
| `achieved/<block>.json` | component | what each block does achieve, with evidence |
| `reviews/<gate>.md` | judge | gate verdicts: `gateA.md`, `gateB.md`, `gateC.md`, `final.md` |
| `work/<role>/` | that role | scratch scripts, sweeps, plots |
| `journal.jsonl` | everyone, via `python tools/team.py log` | one line per decision or result |
| `LESSONS.md` | everyone (append only) | traps and fixes, read first |

## targets/<block>.json

```json
{"block": "coupler_1", "owner": "component",
 "target": {"power_coupling": {"value": 0.50, "tol": 0.02}, "loss_db": {"max": 0.2}},
 "band_um": [1.300, 1.320],
 "why": "first coupler of the lattice; system sim: isolation drops 1 dB per 0.03 error"}
```

## achieved/<block>.json

```json
{"block": "coupler_1", "cell": "library.directional_coupler",
 "params": {"coupling_length": 15.0},
 "achieved": {"power_coupling": 0.489, "loss_db": 0.1},
 "meets_target": true, "margin": "0.011 of 0.02",
 "binding_constraint": "model loss 0.1 dB is fixed by the PDK",
 "evidence": "team/work/component/coupler_1.png"}
```

## reviews/<gate>.md

First line `PASS` or `FIX`. Then numbered issues: where (file:line or plot), what is wrong, evidence,
owner, the fix asked for. Then what is good.
