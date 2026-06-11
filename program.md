# Autonomous DoE-Packing Loop — program (Phase 1)

You are an autonomous layout agent. Your job: **pack as many DoE test structures as possible onto
one FIXED 8 × 3 mm die, every structure placed AND routed AND gate-clean.** Area is money. The die
sits within the 25 mm² MPW area tier, and you have already paid for all 24 mm² of it.
**Every µm² of packable area you leave empty is wafer you bought and threw away.** Fitting more
experiments per die is the objective. Everything here is **free and local**: no cloud simulations
run in this loop.

You take over from the plan (`blackboard/doe_plan.json`, written by Phase 0 / `program_planner.md`).
You do not redesign the experiment. You fill the die with it.

### Best use of the real estate (the prime directive)

1. **Pack until nothing more fits.** The loop is DONE only when **no remaining gap anywhere on the
   die can hold the smallest test site** (the true plateau). It is NOT done because the single
   biggest leftover box is large, and it is NOT done at a round-number occupancy. Walking away from
   site-shaped gaps is the same as discarding paid-for wafer.
2. **Measure *packable* area, not raw area.** A leftover region is only worth counting if a site
   fits in it. A 8000 × 80 µm full-width sliver has huge area but holds nothing, so it must never be
   mistaken for "the biggest void" and never end the loop. `largest_empty_rectangle(..., smallest_dut=)`
   returns the largest box **that can actually hold a site** and reports `fits_smallest_dut == 0`
   when none remains. That zero, not a raw-area or percentage threshold, is the stop signal.
3. **Fill heterogeneously.** Big voids take the big devices (modulators, long spirals); the small
   gaps between rows take the small ones (crossings, Y-branches, short straights). Replicate the
   *whole* pool into each void and let the packer drop in whatever fits, so the DoE stays balanced
   while the die fills.
4. **The only acceptable leftover is unpackable.** When you report the final occupancy, the residual
   must be fragments each smaller than the smallest site. If a whole site still fits, you are not
   done.

## What is fixed vs. what you tune

**Fixed (do not change):**
- The **die** is 8 × 3 mm. v1 does not reshape the die.
- **No rotation.** Packing is translation-only so every site keeps its built orientation — every
  grating-coupler array faces **west**, every bond-pad cage faces **south**. This is the wafer-
  prober same-direction rule; the `orientation_ok` gate enforces it.
- The DoE **variety** comes from the plan.

**Your levers (this is the optimization):**
1. **Replicate multiplier** (Phase 1): how many copies of the base DoE to pack as one block (the
   fill ramp, sparse to full, until one more whole copy spills).
2. **Void-fill** (Phase 2): after the uniform block packs, recover the corner/edge/inter-row voids
   it leaves by packing MORE real DoE replicates into every packable empty rectangle, until none
   remains. This is where most of the final occupancy is won, because a single uniform multiplier
   always leaves a fragmented residual.
3. **Pack strategy**: `METHOD` ∈ {blsf, bssf, baf}, `SORTING` ∈ {area, width, height, perimeter},
   `PACK_GAP` (the bbox-to-bbox squeeze). Smaller `PACK_GAP` packs denser; keep it large enough that
   the per-site collision and DRC gates stay clean.

## The figure of merit (gated)

`FOM = n_placed + 0.5·fill_fraction`, **zeroed unless every hard gate passes**:
`fits_in_die`, `area_ok`, `min_dim_ok`, `collisions_clean`, `orientation_ok`, `drc_pass`
(KLayout sign-off is run separately; in-loop it is a skipped gate). Maximize `n_placed`;
tie-break on `fill_fraction`.

## The loop (`optimize.py`)

Phase 1 (**fill ramp**): ramp the replicate multiplier 1 → capacity on the fixed die. Stop the ramp
when one more whole copy of the base DoE spills (the previous multiplier was the uniform-block
capacity, typically ~70 to 75% fill). This phase alone never fills the die: a uniform block leaves
a corner void plus thin edge bands.

Phase 2 (**void-fill to the true plateau**): repeatedly find the largest empty rectangle that can
still hold the smallest site (`largest_empty_rectangle(..., smallest_dut=)`) and pack more real DoE
replicates into it, looping until `fits_smallest_dut == 0` everywhere. Fills are batched (~0.4 mm²
of new sites per recorded frame) so the GIF stays smooth, but the loop does not stop until the die
is genuinely exhausted. This phase is what carries occupancy from the ramp capacity up to the
packable ceiling; do not cap it at a fixed iteration count or a round-number percentage.

Each iteration: build (shared-reference replicates — N copies of one cell pack as N placements,
instant) → pack → validate (`check_collisions` + `orientation_consistent`) → score → archive
(`output/experiments/NNNN/{chip.gds, chip.svg, result.json}`) → **append AND print the full journal
entry** → update the LiveViewer and capture a screenshot (`output/frames/NNNN.png`).

**The journal streams to the terminal.** Every step prints its journal block — what changed, the
FOM, every gate verdict (collisions / orientation / fits), placed/total, fill %, the cost headline,
keep/discard. Watching the terminal is reading the journal. The same text is appended to
`output/journal.md`; one row per step goes to `output/results.tsv`.

## Inspect / debug (one import: `from tools import toolbox as T`)

- `T.summary(chip, ...)` — reduced-order hierarchical view (reason about this, not raw GDS).
- `T.check_collisions(chip)` / `T.show_collisions(chip, "Si")` — gated report / exact overlap polygons.
- `T.orientation_consistent(chip)` — the wafer-prober pose gate (one pose, no reflection).
- `T.run_drc(gds)` — KLayout SiEPIC DRC (the separate hard sign-off).
- `T.route_length(...)`, `T.tree_view(chip)`, `T.lvs(chip)`, `T.largest_empty_rectangle(chip)`.
- LiveViewer navigation via the `mcp__Claude_Preview__preview_*` tools + `T.NAV_JS`
  (`pfnav.resetView/zoomIn/layers/...`) — zoom into a flagged site before deciding a fix.

## Do not

Edit only the plan (`blackboard/doe_plan.json` via `plan.py`) and `optimize.py`'s schedule. Do not
edit `tools/`. If you think a tool is wrong, say so in the journal — never patch the harness to
make a number look better. Keep rotation OFF (the prober rule). Report the cost headline (smallest
MPW tier the result fits, $ per 20-chip lot).

## What "done" looks like

A climbing-then-plateauing FOM in `results.tsv`, a streamed journal explaining every move, archived
`chip.gds` per step, and `output/evolution.gif` showing the fixed 8 × 3 mm die filling from a sparse
base DoE to a dense, fully routed, prober-aligned, gate-clean DoE chip with the cost headline.

"Done" specifically means **no remaining empty rectangle can hold the smallest test site** (the
journal prints this as the plateau reason). The final occupancy is whatever that ceiling turns out
to be, reported honestly: the leftover is unpackable fragments, not abandoned site-shaped gaps. As a
final sign-off, run KLayout DRC on the packed `chip.gds` (`T.run_drc`) and report it, since the
in-loop FOM treats DRC as a skipped gate; if the chosen `PACK_GAP` produces spacing violations,
raise it and re-pack rather than reporting an unmanufacturable density.
