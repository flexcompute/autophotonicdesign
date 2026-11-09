# Program: run a needle-in-a-haystack review

You are the lead. You plant mistakes in a clean layout, give the planted layout to a team of five blind reviewers,
and score what they find. The reviewers never see the plants.

## Input

The human gives a case and a seed. For example: `case: cases/siepic_mzi_loopback, seed: 7`.
If the human gives no seed, use 1.

## Folders

| Folder | What is in it | Who can read it |
|---|---|---|
| `RED` (outside the repository, for example `~/needle_runs/red/<case>_s<seed>`) | clean layout, planted layout, answer key, scores | only you |
| `SANDBOX` (a new, empty folder, for example `~/needle_runs/<case>_s<seed>`) | planted layout, intent sheet, intended netlist, tools | the reviewers |

Do not put the sandbox in the repository, in `RED` or in a folder that holds other files. A reviewer that lists the
parent folder must see nothing of the red side.

## Steps

1. Plant the mistakes:

   ```bash
   python tools/red/plant.py <case> --seed <seed> --out <RED>
   ```

   The script prints each plant with its kind (mistake, easy, harmless), its severity and the checks that flag it.
   If the clean design fails DRC or LVS, the script stops. Fix the case first.

2. Make the sandbox:

   ```bash
   python tools/make_sandbox.py <RED> <SANDBOX>
   ```

3. Start five reviewers at the same time, as sub-agents. Use one file of `agents/` for each:
   `rules`, `twins`, `microscope`, `intent`, `physics`. Give each reviewer:
   - the text of its file in `agents/`;
   - the path of the sandbox;
   - the rules: read and write only in the sandbox and the installed Python packages; no other folder, no git
     history, no web, no cloud simulations; post findings as they find them; write a summary at the end.

   Do not give a reviewer anything from `RED`, from `cases/` or from `tools/red/`. Do not give hints about the plants.

4. Write the reviewers' transcript paths to `<RED>/agents.json`:
   `{"tasks": "<folder of the transcripts>", "agents": {"rules": "<id>", ...}}`.

5. When all five reviewers stop, score the board and audit the transcripts:

   ```bash
   python tools/red/score.py <RED> <SANDBOX>
   python tools/red/audit.py <RED> <SANDBOX>
   python tools/red/plant_map.py <RED> <RED>/plants_found.png
   ```

6. Look at each finding that matches no plant (`unmatched_findings` in `score.json`). Decide if it is a real problem of
   the clean design or a false alarm. Write the reason in `<RED>/adjudication.json` for each one that is not a false
   alarm, and run the score again.

7. Write `<RED>/REPORT.md`: the plants found and missed, the severities, the false alarms, the tool calls, the time,
   the cost and the audit result.

## Requirements

1. The reviewers work only from the sandbox. One access outside it voids the run. The audit shows each access.
2. You do not change the plants after the reviewers start.
3. You do not tell the reviewers how many plants there are or what kind.
4. A plant is found only when a finding on the board points to its place (within 10 um) with evidence.
