"""Make the reviewers' sandbox from a planter output folder. Only the planted chip, the intent and the tools go in.

    python tools/make_sandbox.py ../runs/siepic_s7/red ../runs/siepic_s7/sandbox

The sandbox gets: chip/haystack.gds, chip/DESIGN_INTENT.md, chip/intent_nets.json, chip/chip.json, tools/review.py,
tools/pdks/<the one PDK>.py, tools/TOOLS.md, tools/env.sh, README.md, board/, work/. Never the answer key, the clean
layout or the planter.
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
README = """\
# Pre-tape-out review: {top} ({pdk})

You are one of {n} reviewers. The chip is `chip/haystack.gds` (top cell `{top}`, {w:.0f} x {h:.0f} um, PDK `{pdk}`).
The design intent is `chip/DESIGN_INTENT.md` and the intended netlist is `chip/intent_nets.json`.

Your job: find everything a careful reviewer must raise before this goes to the fab, especially what DRC and LVS do not
catch (the work a designer otherwise does by hand: lengths, widths, junctions, bends, layers, matching, pitch, anything
that breaks the intent). For each finding, say how bad it is for the chip.

## Rules of the sandbox

- Read and write only inside this folder. Write your scripts and pictures in `work/<your name>/`.
- You may also read the installed Python packages (PhotonForge, Tidy3D, the PDK package) and their documentation.
- Do not read any other folder, any session scratchpad, any `.claude` folder, any git history or any other agent's
  transcript. Do not call local web servers. Every file access is audited afterwards; one access outside these rules
  voids your results.
- Do not edit `chip/` or `tools/`. Do not run cloud simulations. Local mode solves are fine.

## Tools

`tools/TOOLS.md` lists them. Start with:

```
cd <this folder>
source tools/env.sh
$PY -c "import review as rv, json; print(json.dumps(rv.summary(), indent=1))"
```

## Reporting

Post each finding as you find it, with the tool:

```
$PY -c "import review as rv; rv.post(reviewer='<your name>', id='<your name>-1', title='...', category='...',
        bbox=[x0, y0, x1, y1], evidence='what you measured, with numbers and the call', severity='high',
        confidence=0.9, drc_or_lvs_flags_it=False, impact='what it does to the chip', fix='...')"
```

or write one JSON object per line to `board/<your name>.jsonl` with the same fields.

Severity: **high** = more than 1 dB on a path, a dead path, or a circuit that does not do its function;
**medium** = 0.1 to 1 dB, or a reliability or matching risk; **low** = a rule or intent violation with a small or
tunable effect; **none** = a difference that does no harm (say so: to report a harmless difference as harmless is good
work).

Every finding needs a location precise to a few um and evidence. False alarms count against you; so does rating a
harmless difference as a defect, or a defect as harmless. Other reviewers post to `board/` too: read their findings
(`rv.board()`), confirm or dispute with evidence (`confirms='<id>'` or `disputes='<id>'`), and do not post a finding
twice (refer to its id).

At the end write `board/<your name>_summary.md`: what you checked, how (tools, and what fraction of the chip each check
covered), what you found, what you could not check.
"""

TOOLS_MD = """\
# Tools

All in `review.py` (`import review as rv` after `source tools/env.sh`). Coordinates in um, in the frame of the top cell.
First calls build a cache (a few seconds); later calls are fast.

| Call | What it gives you |
|---|---|
| `rv.summary()` | PDK, wavelength, route spec, chip bbox, shapes per layer, cell families, whether a DRC deck exists |
| `rv.chip()`, `rv.tech()`, `rv.pdk()` | the PhotonForge top Component (hierarchy kept), the Technology, the PDK adapter |
| `rv.instances()` | every placed cell at every level: path (as the extraction names it), cell, origin, angle, mirrored, bbox, device |
| `rv.find(cell_prefix, bbox)` | instances filtered by cell-name prefix and/or region |
| `rv.cell_shapes(cell_name)` | the shapes of one cell in its own frame, by layer (shapely polygons) |
| `rv.flat()` | every shape on the chip by layer name, as shapely polygons |
| `rv.query(bbox, layers)` | shapes that overlap a region: layer, bounds, area, vertex count, polygon |
| `rv.cross_section(x, y, direction_deg, layers, span)` | material on a cut across a waveguide that runs at direction_deg: width and position |
| `rv.route_width()` | the core width of the route waveguide of this PDK |
| `rv.centerline_length(polygon, width)` | area / width |
| `rv.fingerprint(shapes_by_layer)` | a geometry hash that ignores translation: equal shapes give equal hashes |
| `rv.render(bbox, out_png, layers, px, marks, outline)` | a picture of any region at any zoom. Look at it with your image reader |
| `rv.drc()` | the PDK DRC deck when there is one, else the basic width and space check: counts per rule and marker boxes |
| `rv.basic_drc(rules)` | minimum width and space on any layer, with your own numbers |
| `rv.extraction()` | the optical and electrical nets extracted from the layout, and the position of every device pin |
| `rv.lvs()` | layout nets against `chip/intent_nets.json`: mismatched nets and unconnected pins |
| `rv.pin_xy("cell#i.pin")` | where a device pin is |
| `rv.optical_net_geometry()` | every optical net: its pins, the routing shapes between them, approximate length, layers, bbox |
| `rv.modes(width, bend_radius, num_modes)` | local Tidy3D mode solve of this PDK's route cross-section (no cloud, about 5 to 20 s) |
| `rv.junction_loss(width1, width2, offset, layer2)` | loss where two cross-sections meet end to end (mode overlap), with a side offset |
| `rv.bend_loss(radius, angle_deg)` | loss of one bend: radiation along the arc and the mode mismatch at its two ends |
| `rv.mode_fields(width, bend_radius, layer)`, `rv.overlap(a, b, offset)` | the solved modes for your own overlap calculations, and the overlap of two of them |
| `rv.post(...)`, `rv.board()` | post a finding to the shared board, read the board |

You can write any further analysis yourself (shapely, numpy, PhotonForge, Tidy3D local mode solver). Keep your scripts in
`work/<your name>/`.
"""


def main(red, dst, n_reviewers=5, python=sys.executable):
    red, dst = Path(red).resolve(), Path(dst).resolve()
    key = json.loads((red / "answer_key.json").read_text())
    if dst.exists():
        shutil.rmtree(dst)
    for d in ("chip", "tools/pdks", "board", "work", "cache"):
        (dst / d).mkdir(parents=True, exist_ok=True)
    shutil.copy(red / "haystack.gds", dst / "chip" / "haystack.gds")
    shutil.copy(red / "DESIGN_INTENT.md", dst / "chip" / "DESIGN_INTENT.md")
    shutil.copy(red / "intent_nets.json", dst / "chip" / "intent_nets.json")
    (dst / "chip" / "chip.json").write_text(json.dumps(dict(gds="haystack.gds", top=key["top"], pdk=key["pdk"],
                                                            intent_nets="intent_nets.json"), indent=1))
    shutil.copy(HERE / "review.py", dst / "tools" / "review.py")
    shutil.copy(HERE / "pdks" / "__init__.py", dst / "tools" / "pdks" / "__init__.py")
    shutil.copy(HERE / "pdks" / f"{key['pdk']}.py", dst / "tools" / "pdks" / f"{key['pdk']}.py")
    (dst / "tools" / "TOOLS.md").write_text(TOOLS_MD)
    (dst / "tools" / "env.sh").write_text(
        "# source tools/env.sh (from the sandbox folder): sets $PY and the import path for review.py\n"
        'SANDBOX="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"\n'
        f"export PY={python}\n"
        'export PYTHONPATH="$SANDBOX/tools"\n'
        "export MPLBACKEND=Agg\n")
    sys.path.insert(0, str(HERE))
    import review as rv
    rv.configure(dst / "chip" / "haystack.gds", key["top"], key["pdk"], cache=red / "cache_sandbox_probe")
    x0, y0, x1, y1 = rv.summary()["bbox"]
    (dst / "README.md").write_text(README.format(top=key["top"], pdk=key["pdk"], n=n_reviewers, w=x1 - x0, h=y1 - y0))
    print("sandbox:", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *(int(a) for a in sys.argv[3:4]))
