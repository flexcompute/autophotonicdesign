"""
optimize.py  ──  the autonomous DoE-packing loop (v1: fixed 8x3 mm die, plan-driven).

Goal: pack as many placed-AND-routed-AND-clean DoE structures as possible onto a FIXED
8 x 3 mm = 24 mm^2 die (within the 25 mm^2 MPW area tier), maximizing area occupancy AND the FOM
(DoE device count). The die shape is fixed; rotation is OFF and stays off (every site keeps its
built orientation -> the wafer-prober same-direction rule, checked by `orientation_consistent`).

Two phases, run until occupancy PLATEAUS (not a fixed iteration count):

  PHASE 1 — FILL RAMP: ramp the replicate multiplier 1 -> capacity. The die fills from sparse to
            packed; `pf.pack_layout` (blsf) leaves a corner void at capacity (~73% fill).
  PHASE 2 — VOID-FILL: recursively find the largest empty rectangle in the usable area and plug it
            with MORE real DoE replicates, until the largest remaining void is smaller than the
            smallest test site (the occupancy plateau, ~85%). Every added site is a real DoE device
            (no inert fillers) so the FOM keeps climbing. Each round is validated BEFORE it commits.

Each step: build/assemble -> validate (collisions + orientation) -> score -> archive (gds/svg/json)
-> **append AND print the full journal entry** (the user watches the reasoning live) -> update the
LiveViewer and capture a screenshot. At the end, stitch the frames into a captioned GIF.

Usage:  python optimize.py [max_steps]
"""
import sys
import json
import time
import pathlib
import warnings

warnings.filterwarnings("ignore", message=".*renamed in the layout.*")
ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

import photonforge as pf
from photonforge.live_viewer import LiveViewer
from tools import components, library, test_structures, floorplan, criteria, validation
from tools import toolbox as T

OUT = ROOT / "output"
FRAMES = OUT / "frames"
PLAN_PATH = ROOT / "blackboard" / "doe_plan.json"
PORT = 8767
DICE = floorplan.DICE_MARGIN
AREA_BUDGET = 25.0
MIN_DIM = 2000.0
ALLOW_ROTATION = False          # LOCKED: same prober direction for every site
GAP = 8.0                        # pack gap (bbox-to-bbox; real geometry is further apart)
VF_CELL = 20.0                   # void-fill raster cell (finer = captures more fragmented free space)
PLATEAU_PP = 0.003               # stop void-fill when a round adds < 0.3 percentage-points fill


def load_plan():
    if not PLAN_PATH.exists():
        sys.exit("no blackboard/doe_plan.json — run `python plan.py` first (Phase 0).")
    return json.loads(PLAN_PATH.read_text())


# ── metrics / assembly helpers ───────────────────────────────────────────────
def metrics_of(chip, die_w, die_h):
    """Recompute placement metrics from a chip's current site references (used after void-fill,
    where the chip grew beyond the original pack)."""
    refs = chip.references
    n = len(refs)
    placed_area = sum((b1 - b0) * (d1 - d0)
                      for (b0, d0), (b1, d1) in (r.bounds() for r in refs))
    return {"n_placed": n, "n_total": n, "n_spilled": 0,
            "die_w_um": die_w, "die_h_um": die_h, "die_area_mm2": die_w * die_h / 1e6,
            "fill_fraction": placed_area / (die_w * die_h)}


def snapshot_refs(chip):
    """Capture a chip's site references as (component, origin) — all rotation 0 (no-rotation pack)."""
    return [(r.component, (float(r.origin[0]), float(r.origin[1]))) for r in chip.references]


def assemble(base_refs, vf_placements, die_w, die_h):
    """Build a fresh chip from base + void-fill placements (non-destructive). Draws the die
    boundary + FloorPlan so frames show the fixed footprint and the dicing keep-out."""
    c = pf.Component("doe_chip")
    for comp, origin in base_refs:
        r = c.add_reference(comp)
        r.origin = origin
    for comp, origin in vf_placements:
        r = c.add_reference(comp)
        r.origin = origin
    (x0, y0), (x1, y1) = c.bounds()
    dminx, dminy = x0 - DICE, y0 - DICE
    c.add(floorplan.DIE_LAYER, pf.Rectangle((dminx, dminy), (dminx + die_w, dminy + die_h)))
    c.add(floorplan.FLOORPLAN_LAYER,
          pf.Rectangle((dminx + DICE, dminy + DICE),
                       (dminx + die_w - DICE, dminy + die_h - DICE)))
    return c


def floorplan_region(chip):
    """Usable-area rectangle (the FloorPlan (99,0) bounds) — the search window for void-filling."""
    polys = validation.layer_polygons(chip, floorplan.FLOORPLAN_LAYER)
    if not polys:
        return None
    bs = [p.bounds() for p in polys]
    return ((min(b[0][0] for b in bs), min(b[0][1] for b in bs)),
            (max(b[1][0] for b in bs), max(b[1][1] for b in bs)))


def evaluate(plan, lib, *, mult, gap, method, sorting):
    """Phase-1 build+pack+validate+score at a replicate multiplier."""
    die_w, die_h = plan["die"]["DIE_W"], plan["die"]["DIE_H"]
    structs, meta = test_structures.build_from_plan(plan, lib, replicates=mult)
    chip, metrics = floorplan.pack_into_die(
        structs, die_w=die_w, die_h=die_h, gap=gap, sorting=sorting,
        method=method, allow_rotation=ALLOW_ROTATION)
    col = validation.check_collisions(chip)
    orient = validation.orientation_consistent(chip)
    drc = validation.DRCReport(available=False, error="opt loop (KLayout sign-off run separately)")
    score = criteria.score_chip(chip, metrics, col, drc, orient,
                                area_budget_mm2=AREA_BUDGET, min_dim_um=MIN_DIM)
    return chip, metrics, meta, col, orient, score


def score_assembled(chip, die_w, die_h):
    """Score an assembled (void-filled) chip from its current references."""
    metrics = metrics_of(chip, die_w, die_h)
    col = validation.check_collisions(chip)
    orient = validation.orientation_consistent(chip)
    drc = validation.DRCReport(available=False, error="opt loop")
    score = criteria.score_chip(chip, metrics, col, drc, orient,
                                area_budget_mm2=AREA_BUDGET, min_dim_um=MIN_DIM)
    return metrics, col, orient, score


# ── journal entry (written to journal.md AND streamed to the terminal) ────────
def journal_entry(n, phase, change, score, col, orient, mult, decision):
    tier = criteria.mpw_area_tier(score.die_area_mm2)
    return "\n".join([
        f"## step {n:02d} [{phase}] — {change}",
        f"- **FOM {score.fom:.1f}**  ({'PASS' if score.passes else 'FAIL'})   "
        f"decision: **{decision}**",
        f"- placed {score.n_placed}  fill {score.fill_fraction*100:.1f}%  "
        f"on {score.die_w_um/1000:.0f}x{score.die_h_um/1000:.0f}mm "
        f"({score.die_area_mm2:.0f}mm2, {tier}mm2 MPW area tier)",
        f"- gates: fits={'OK' if score.fits_in_die else 'SPILL'}  "
        f"{col.summary()}  {orient.summary()}",
        f"- pack: replicate x{mult}  gap={GAP:.0f}um  method=blsf  rotation=OFF",
    ])


def main():
    max_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    # clear stale outputs so frames + experiments only reflect THIS run (else a longer prior run
    # leaves higher-numbered experiment dirs that view_last / the GIF would pick up)
    import shutil
    for d in (OUT / "experiments", FRAMES):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
    components.technology()
    lib = library.default_library()
    plan = load_plan()
    die_w, die_h = plan["die"]["DIE_W"], plan["die"]["DIE_H"]
    usable = (die_w - 2 * DICE) * (die_h - 2 * DICE)
    print(f"target: maximize occupancy of the fixed {die_w/1000:.0f}x{die_h/1000:.0f}mm die "
          f"(usable {usable/1e6:.1f}mm2); ramp replicates to capacity, then void-fill to the "
          f"plateau. rotation OFF.\n")

    journal = OUT / "journal.md"
    journal.write_text(
        "# DoE-packing journal (v1, optimize.py)\n\n"
        "Maximize area occupancy + FOM (DoE device count) on a FIXED 8x3 mm die. Phase 1: ramp "
        "replicates to capacity. Phase 2: void-fill the largest empty rectangles with more real DoE "
        "replicates until occupancy plateaus. Rotation OFF (same prober direction every site). "
        "Each entry is streamed to the terminal as the loop runs.\n")
    results_tsv = OUT / "results.tsv"
    results_tsv.write_text("step\tphase\tfom\tplaced\tfill%\tmult\torient\tchange\n")

    # void-fill pool = the base DoE (every device once); repeated to fill a void.
    pool, _ = test_structures.build_from_plan(plan, lib, replicates=1)
    pool_dims = [s.bounds() for s in pool]
    min_w = min(b[1][0] - b[0][0] for b in pool_dims)
    min_h = min(b[1][1] - b[0][1] for b in pool_dims)

    viewer = LiveViewer(port=PORT)

    # Frame capture for the evolution GIF screenshots the LiveViewer via Playwright. It is OPTIONAL:
    # without Playwright/Chromium the loop runs headless and simply skips the PNG frames. Enable it
    # with `pip install playwright && playwright install chromium`.
    import contextlib
    pw_ctx, page = contextlib.nullcontext(), None
    try:
        from playwright.sync_api import sync_playwright
        pw_ctx = sync_playwright()
    except Exception as e:  # noqa: BLE001
        print(f"(frame capture off: Playwright unavailable, {e}); running headless\n", flush=True)

    best = {"fom": -1}
    final_chip = None
    n = 0
    with pw_ctx as pw:
        browser = None
        if pw is not None:
            try:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={"width": 1200, "height": 1100},
                                        device_scale_factor=2, color_scheme="dark")
                page.goto(f"http://localhost:{PORT}")
                time.sleep(2)
                try:
                    page.evaluate(
                        "() => { if (getComputedStyle(document.body).backgroundColor === 'rgb(255, 255, 255)') {"
                        "const b = Array.from(document.querySelectorAll('button')).find("
                        "e => ((e.title||'').toLowerCase()).includes('theme')); if (b) b.click(); } }")
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(0.5)
            except Exception as e:  # noqa: BLE001
                print(f"(frame capture off: browser launch failed, {e}); running headless\n", flush=True)
                page = None

        def record(chip, score, col, orient, *, phase, change, mult, decision):
            nonlocal n, best, final_chip
            final_chip = chip
            exp = OUT / "experiments" / f"{n:04d}"
            exp.mkdir(parents=True, exist_ok=True)
            chip.write_gds(str(exp / "chip.gds"))
            (exp / "chip.svg").write_text(chip._repr_svg_())
            tier = criteria.mpw_area_tier(score.die_area_mm2)
            (exp / "result.json").write_text(json.dumps({
                "exp": n, "phase": phase, "change": change, "fom": score.fom,
                "passes": score.passes, "n_placed": score.n_placed, "n_unique": "?",
                "die_w_um": score.die_w_um, "die_h_um": score.die_h_um,
                "die_area_mm2": round(score.die_area_mm2, 3),
                "fill_fraction": round(score.fill_fraction, 4),
                "collisions_clean": score.collisions_clean, "orientation_ok": score.orientation_ok,
                "mpw_tier_mm2": tier,
                "design": {"REPLICATE_MULT": mult, "PACK_GAP": GAP, "METHOD": "blsf",
                           "ALLOW_ROTATION": ALLOW_ROTATION, "DIE_W": score.die_w_um,
                           "DIE_H": score.die_h_um},
            }, indent=2))
            entry = journal_entry(n, phase, change, score, col, orient, mult, decision)
            with journal.open("a") as f:
                f.write("\n" + entry + "\n")
            with results_tsv.open("a") as f:
                f.write(f"{n}\t{phase}\t{score.fom:.1f}\t{score.n_placed}\t"
                        f"{score.fill_fraction*100:.1f}\t{mult}\t{score.orientation_poses}\t{change}\n")
            print("\n" + "─" * 78)
            print(entry)
            print("─" * 78, flush=True)
            viewer(chip)
            if page is not None:
                _capture(page, FRAMES / f"{n:04d}.png")
            if score.passes and score.fom > best["fom"]:
                best = {"fom": score.fom, "step": n, "n": score.n_placed,
                        "fill": round(score.fill_fraction, 4), "phase": phase}
            n += 1

        # ── PHASE 1: fill ramp ──
        cap_chip, cap_mult = None, 1
        for mult in range(1, 19):
            chip, metrics, meta, col, orient, score = evaluate(
                plan, lib, mult=mult, gap=GAP, method="blsf", sorting="area")
            if score.n_spilled > 0:
                break                       # previous mult was capacity
            change = f"fill ramp: replicate x{mult}  ({score.n_placed} devices)"
            record(chip, score, col, orient, phase="fill", change=change, mult=mult,
                   decision="KEEP" if (score.passes and score.fom > best["fom"]) else "ok")
            cap_chip, cap_mult, cap_meta = chip, mult, meta
            if n >= max_steps:
                break

        # ── PHASE 2: void-fill to the plateau ──
        # Plug EVERY packable void, not just the single largest. Each round, the inner loop keeps
        # finding the largest rectangle that can still hold the smallest site and fills it, until
        # no such rectangle remains anywhere (the TRUE plateau) — the previous code quit after one
        # round because `largest_empty_rectangle` returned the biggest void *by raw area*, which is
        # an unusable full-width sliver, so site-shaped gaps were abandoned. Fills are batched to
        # ~STEP_AREA per recorded frame so the GIF stays smooth without one frame per tiny gap.
        STEP_AREA = 0.40e6           # µm^2 of new sites per recorded frame (~1.7pp of a 24mm2 die)
        if cap_chip is not None and n < max_steps:
            base_refs = snapshot_refs(cap_chip)
            region = floorplan_region(cap_chip)
            vf, prev_fill, rnd = [], metrics_of(cap_chip, die_w, die_h)["fill_fraction"], 0
            while n < max_steps:
                batch, batch_voids, batch_area = [], 0, 0.0
                while True:          # inner: exhaust packable voids until this frame has filled ~STEP_AREA
                    work = assemble(base_refs, vf + batch, die_w, die_h)
                    ler = T.largest_empty_rectangle(work, gap=GAP, cell=VF_CELL, region=region,
                                                    smallest_dut=(min_w, min_h))
                    if ler["fits_smallest_dut"] < 1:    # no rectangle can hold even the smallest site
                        break
                    k = max(1, min(400, int(ler["w_um"] * ler["h_um"] / (min_w * min_h)) + len(pool)))
                    sub, _ = floorplan.pack_into_die(
                        (pool * (k // len(pool) + 1))[:k], die_w=ler["w_um"], die_h=ler["h_um"],
                        gap=GAP, method="blsf", sorting="area", allow_rotation=False,
                        draw_boundary=False, dice_margin=0.0)
                    new = [(r.component, (ler["x0"] + float(r.origin[0]), ler["y0"] + float(r.origin[1])))
                           for r in sub.references]
                    if not new:
                        break
                    batch += new
                    batch_voids += 1
                    for comp, _o in new:
                        (bx0, by0), (bx1, by1) = comp.bounds()
                        batch_area += (bx1 - bx0) * (by1 - by0)
                    if batch_area >= STEP_AREA:
                        break
                if not batch:
                    print(f"\nvoid-fill plateau: no remaining void can hold the smallest "
                          f"{min_w:.0f}x{min_h:.0f}um site — every packable gap is used. done.",
                          flush=True)
                    break
                trial = assemble(base_refs, vf + batch, die_w, die_h)
                metrics, col, orient, score = score_assembled(trial, die_w, die_h)
                if not col.clean:           # safety: should not happen (gap-inflated LER)
                    print(f"\nvoid-fill round {rnd} introduced collisions ({col.summary()}) — "
                          f"discarding it and stopping.", flush=True)
                    break
                gain = score.fill_fraction - prev_fill
                vf += batch
                change = (f"void-fill rnd {rnd}: +{len(batch)} DoE sites across {batch_voids} "
                          f"void(s)  (+{gain*100:.1f}pp -> {score.fill_fraction*100:.1f}%)")
                record(trial, score, col, orient, phase="void-fill", change=change,
                       mult=f"{cap_mult}+vf", decision="KEEP" if score.fom > best["fom"] else "ok")
                if gain < PLATEAU_PP:
                    print(f"\nvoid-fill plateau: round added only {gain*100:.2f}pp fill — done.",
                          flush=True)
                    break
                prev_fill, rnd = score.fill_fraction, rnd + 1
        if browser is not None:
            browser.close()

    if final_chip is not None:
        write_doe_summary(final_chip, plan, lib, die_w, die_h)
    print(f"\nBEST: step {best.get('step')}  FOM {best.get('fom')}  {best.get('n')} structures  "
          f"fill {best.get('fill', 0)*100:.1f}%  ({best.get('phase')})")
    (OUT / "best.json").write_text(json.dumps(best, indent=2))
    print("next: python make_gif_from_frames.py 1.8   (stitch the LiveViewer frames into evolution.gif)")
    return best


def write_doe_summary(chip, plan, lib, die_w, die_h):
    """Tabulate the DoE actually realized on the final packed chip.

    Every site's component name == its DoE tag (replicates share the cell), so counting references
    by name gives the exact number of each variation placed (base replicates + void-fill copies).
    Writes output/doe_summary.md (per-experiment + per-variation tables) and doe_summary.csv.
    """
    from collections import Counter
    import csv as _csv
    counts = Counter(r.component.name for r in chip.references)
    metrics = metrics_of(chip, die_w, die_h)
    tier = criteria.mpw_area_tier(die_w * die_h / 1e6)

    # per-variation rows, in plan order; tag mirrors build_from_plan
    variations, experiments = [], []
    for e in plan["experiments"]:
        src, param = e["source"], e.get("param")
        fixed = e.get("fixed", {}) or {}
        exp_sites = 0
        vals = []
        for v in e["values"]:
            tag = f"{src}" + (f"_{param}{v}" if (param and v is not None) else "")
            sites = counts.get(tag, 0)
            exp_sites += sites
            vals.append("replicate" if v is None else v)
            variations.append({"label": test_structures.short_label(src, param, v),
                               "device": src, "parameter": param or "(replicate)",
                               "value": ("—" if v is None else v),
                               "fixed": ", ".join(f"{k}={vv}" for k, vv in fixed.items()) or "—",
                               "sites": sites, "measures": e["measures"]})
        experiments.append({"device": src, "kind": e["kind"], "measures": e["measures"],
                            "parameter": param or "(replicate)", "values": vals,
                            "n_values": len(e["values"]), "sites": exp_sites})
    total = sum(v["sites"] for v in variations)

    md = [f"# Final DoE — packed test chip\n",
          f"**{len(chip.references)} structures** placed + routed + DRC-clean on a fixed "
          f"**{die_w/1000:.0f} x {die_h/1000:.0f} mm = {die_w*die_h/1e6:.0f} mm²** die "
          f"({metrics['fill_fraction']*100:.1f}% area occupancy, {tier} mm² MPW area tier "
          f"MPW tier). All sites share one orientation (wafer-prober aligned). "
          f"{sum(1 for e in experiments if e['kind']=='pcell')} PCell + "
          f"{sum(1 for e in experiments if e['kind']=='gds')} GDS device experiments.\n",
          "## DoE by experiment\n",
          "| device | source | measures | parameter | values | sites |",
          "|--------|--------|----------|-----------|--------|------:|"]
    for e in experiments:
        vals = ", ".join(str(x) for x in e["values"])
        md.append(f"| {e['device']} | {e['kind']} | {e['measures']} | `{e['parameter']}` "
                  f"| {vals} | {e['sites']} |")
    md.append(f"| **total** | | | | | **{total}** |")
    md += ["\n## DoE by variation (every swept point + how many landed)\n",
           "| label | device | setting | sites |", "|-------|--------|---------|------:|"]
    for v in variations:
        setting = "replicate" if v["parameter"] == "(replicate)" else f"{v['parameter']}={v['value']}"
        if v["fixed"] != "—":
            setting += f"  ({v['fixed']})"
        md.append(f"| `{v['label']}` | {v['device']} | {setting} | {v['sites']} |")
    (OUT / "doe_summary.md").write_text("\n".join(md) + "\n")

    with open(OUT / "doe_summary.csv", "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=["label", "device", "parameter", "value", "fixed",
                                           "sites", "measures"])
        w.writeheader()
        for v in variations:
            w.writerow({k: v[k] for k in w.fieldnames})
    print(f"\nwrote output/doe_summary.md + doe_summary.csv  ({total} sites across "
          f"{len(variations)} variations)")


def _capture(page, frame_path, *, max_wait=14.0):
    """Capture the LiveViewer after a viewer(chip) push (reload re-fits the whole die in frame)."""
    try:
        page.reload()
        page.wait_for_selector("canvas", timeout=15000)
        end = time.time() + max_wait
        while time.time() < end:
            try:
                body = page.inner_text("body", timeout=800)
            except Exception:  # noqa: BLE001
                body = ""
            if "inaliz" not in body and "endering" not in body:
                break
            time.sleep(0.3)
        time.sleep(1.0)
        page.screenshot(path=str(frame_path))
    except Exception as e:  # noqa: BLE001
        print(f"    capture failed: {e}")


if __name__ == "__main__":
    main()
    # The LiveViewer keeps a non-daemon server thread alive, which would block process exit
    # (the loop's work + all archiving is already flushed). Force a clean exit so the run
    # actually terminates instead of lingering.
    import os
    os._exit(0)
