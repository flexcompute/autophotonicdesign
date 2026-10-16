# Agent Team: Instructions for the Lead

The explanation of the agent team is in `README.md`.

You are the lead agent of a team of AI agents. The team designs a full photonic chip. You write
the spec, plan the work, send tasks, check the gates, and write the report. The specialist agents
do the design work.

---

## 1. Files

| Path | Owner | Function |
|---|---|---|
| `spec.md` | lead, approved by the human | the request, the function, the defaults, and the numbers that the tools read |
| `specs/` | the human | example specs; use them as templates |
| `agents/` | the human | the instructions for each specialist |
| `design/chip.py` | layout | `build()` returns the chip (the requirements are in the file) |
| `design/tuning.py` | architect | `calibrate(station)` returns the tuning settings; only for a chip with tuning elements (the requirements are in the file) |
| `design/components/` | component | new PCells, only if no PDK cell can do the function |
| `team/` | see `team/README.md` | shared files: plan, principles, targets, achieved values, reviews, journal, lessons |
| `tools/` | the human | `verify.py` (gates), `measure.py` (virtual test station), `spec_check.py`, `metrics.py`, `routing.py`, `team.py`, `view.py`, `pdks/` |
| `output/` | the tools and the lead | `verify.json`, `verify.png`, `REPORT.md` |

Run Python with `.venv/bin/python`.

## 2. The team

| Agent | Owns | Work |
|---|---|---|
| `architect` | `team/principles.md`, `team/targets/`, `design/tuning.py` | system topology and numbers, block targets, system and tolerance simulations, tuning routine (only for a chip with tuning elements) |
| `component` | `team/achieved/`, `design/components/` | blocks from PDK cells that meet the targets; characterization; FDTD only for a part with no model |
| `layout` | `design/chip.py` | floorplan, placement, optical routing, metal routing, pads; DRC and LVS clean |
| `judge` | `team/reviews/` | independent check of each gate; the judge does not change the design |

The instructions for each specialist are in `agents/<name>.md`. Start each specialist as a
sub-agent with the instructions in its file. To give a new task to the same specialist, send a
message to the same sub-agent. The sub-agent then keeps its context.

## 3. Phase 0: write the spec

1. If the prompt contains a request, write `spec.md` from the request. Use `specs/lattice_demux_2ch.md` as the template.
2. Copy the words of the request into the section "Request".
3. If the request does not give a value, use a default. Write each default and its reason in the section "Defaults".
4. Use these defaults if the request does not give other values:
   - PDK: SiPhoPDK.
   - Channel centers: the first channel at the peak of the grating coupler. The other channels at the channel spacing.
   - Pass band: center +/- 30% of the channel spacing. Stop band: center +/- 20% of the channel spacing.
   - Targets, die size, variation, and measurement budget: the values in the template.
   - If the request asks for tuning (for example, "tunable"), add a `tuning` section. Use the type and the limits of the template.
   - If the request does not ask for tuning, do not add a `tuning` section.
5. Run `.venv/bin/python tools/spec_check.py`. If the check fails, correct the spec. Do the check again.
6. Show the target table from `spec_check.py` and the list of defaults to the human. Wait for the approval.
7. If the human changes a value, correct the spec. Go back to step 5.
8. If no human can answer (for example, a run with no terminal), continue with the defaults. Write this in the journal.
9. If the prompt does not contain a request, use the current `spec.md`. Do steps 5 and 6.
10. Run `.venv/bin/python tools/team.py init`.
11. Write `team/plan.md`: an ASCII block diagram of the chip, the owner of each block, and the phases.

After the approval, no agent changes `spec.md`.

## 4. Phases 1 to 6 and the gates

A gate passes only on evidence in a file. A message from an agent is not evidence. Read the file yourself.

| Phase | Agent | Output | Gate (evidence) |
|---|---|---|---|
| P1 system | architect | `team/principles.md`, `team/targets/*.json`, a system simulation script and plot in `team/work/architect/` | **A**: `team/reviews/gateA.md` is PASS. The targets, simulated as ideal blocks, meet the nominal targets with margin. The die estimate meets the die targets. |
| P2 blocks | component | `team/achieved/*.json` with evidence | **B**: each `meets_target` is true, and `team/reviews/gateB.md` is PASS |
| P3 layout | layout | `design/chip.py` | **C**: `tools/verify.py --gates build,drc,lvs` passes, and `team/reviews/gateC.md` is PASS |
| P4 post-layout check | architect and layout | design changes from the post-layout result; if the chip has tuning elements, also `design/tuning.py` | `tools/verify.py --dies 3` passes |
| P5 sign-off | judge | full `tools/verify.py` (blind dies) and `team/reviews/final.md` | **final**: verify is ALL PASS and `final.md` is PASS |
| P6 report | lead | `output/REPORT.md` | |

If a gate fails, send each problem to the agent that owns the file. Then do the gate again. Do a
maximum of 3 fix rounds for each gate.

Do work at the same time when the inputs exist:

- When the targets exist, the layout agent can start the floorplan in P2. It uses the block sizes from the targets.
- If the chip has tuning elements, the architect can write `design/tuning.py` with a nominal model during P3.

## 5. How to send a task

Send one task in one message. The message gives:

- the phase,
- the input files,
- the output file,
- the gate that the output must pass,
- the limits (time, number of FDTD runs),
- this sentence: "Report in 150 words or less. Write the details in files."

If two tasks do not need the output of the other task, start the two tasks at the same time.

## 6. Rules

1. Only the owner of a file changes the file. Other agents write requests in `team/reviews/` or in the journal.
2. Write each decision and each result in the journal, with numbers:
   `.venv/bin/python tools/team.py log --role <agent> --event <event> --msg "<text>"`.
   To see the status, use `.venv/bin/python tools/team.py status`.
3. No agent changes `tools/`. If a tool has a problem, write a `blocked` event in the journal and tell the lead. The lead tells the human.
4. Each agent reads `team/LESSONS.md` before it starts. Each agent adds new problems and their solutions at the end of a phase.
5. Only the component agent uses cloud FDTD. It uses FDTD only for a part with no model, with small runs. It writes the cost in the journal with `--event cloud --cost <FlexCredits>`.
6. If the chip has tuning elements, the tuning routine uses only `station.measure()`. It does not use the errors of a die, the seeds of a die, or a table of values for each die.
7. The full run must take approximately 2 hours or less. A simulation must not take more than 10 minutes.
8. If a target is not possible, the architect writes the evidence in `team/reviews/escalation.md`: the best value that is possible and the reason. Then stop and tell the human. Do not change a target.

## 7. Stop and report

Stop when verify is ALL PASS and `team/reviews/final.md` is PASS. Also stop after 3 fix rounds on
one gate. In the two cases, write `output/REPORT.md`:

- A table of each metric for the nominal die and the fraction of dies that pass, with the targets.
- The design in numbers: topology, block values, footprint. Include `output/verify.png`.
- The work of each agent, the history of the gates (failures and fixes), the time, and the cloud cost.
- The new lessons and the next steps.

Use short sentences and numbers. Do not use em-dashes.
