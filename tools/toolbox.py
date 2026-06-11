"""
toolbox.py  ──  THE single AI tool surface for the DoE-packing harness.

Everything the agent uses to INSPECT, VALIDATE, NAVIGATE, and MEASURE the chip is re-exported
here, so there is one place / one import:

    from tools import toolbox as T
    T.catalog()                       # list every available tool
    T.summary(chip, ...)              # reduced-order hierarchical view
    T.show_collisions(chip, "Si")     # exact boolean overlap regions (LVS style)
    T.run_drc(gds)                    # KLayout SiEPIC DRC
    T.route_length(route_component)   # native physical route length
    T.tree_view(chip)                 # native ASCII hierarchy
    T.lvs(chip)                       # netlist + collisions + dangling -> LVS verdict
    T.largest_empty_rectangle(chip)   # biggest free box to pack more into

The implementations live in cohesive modules (validation / inspect / hierarchy / violations /
viewer / floorplan); this module is the catalogued façade plus the two packing/LVS tools.
"""
import photonforge as pf

# ── collisions + DRC (tools/validation.py) ────────────────────────────────
from .validation import (
    check_collisions, klayout_drc, collision_map, waveguide_collisions,
    collision_regions, overlap_area, bondpad_spacing, layer_polygons, m2_over_m1,
    orientation_consistent,
)
show_collisions = collision_map          # LVS-guide name
run_drc = klayout_drc

# ── reduced-order representation + measurements (tools/inspect.py) ─────────
from .inspect import (
    chip_summary as summary, render_text, route_lengths, localize_drc,
    structure_summary, layer_histogram, _dangling_ports,
)

# ── hierarchy + multi-level validation (tools/hierarchy.py) ───────────────
from .hierarchy import tree_text, find, validate_node, check_all_levels

# ── violation overlay (tools/violations.py) ───────────────────────────────
from .violations import annotate as paint_violations, parse_drc_markers

# ── viewer navigation (tools/viewer.py) ───────────────────────────────────
from .viewer import to_view, NAV_JS

# ── native PhotonForge tools, surfaced by name ────────────────────────────
route_length = pf.route_length
effective_route_length = pf.effective_route_length


def tree_view(component):
    """Native ASCII hierarchy tree."""
    return component.tree_view()


def netlist(component):
    """Native connectivity netlist (instances / ports / connections / virtual connections)."""
    return component.get_netlist()


def bounds(obj):
    """Native bounding box ((x0,y0),(x1,y1)) of any component or reference."""
    return obj.bounds()


# ══════════════════════════════ NEW TOOL 1: packing space ══════════════════
def _max_hist(heights, *, min_w=1, min_h=1):
    """Largest rectangle in a histogram -> (area, left_col, right_col_inclusive, height).

    With `min_w` / `min_h` (in cells), only rectangles at least that wide AND tall are considered,
    and the one with the largest *area* among them wins. Bars shorter than `min_h` are treated as
    walls (height 0) so no returned rectangle is shorter than `min_h`. This is the difference
    between "biggest empty box by raw area" (which can be an unusable full-width sliver) and
    "biggest box that can actually hold a site" — the loop must optimize the latter or it quits on
    a thin strip while site-shaped gaps remain.
    """
    h = [x if x >= min_h else 0 for x in heights]
    stack, best = [], (0, 0, 0, 0)
    for i, x in enumerate(h + [0]):
        start = i
        while stack and stack[-1][1] > x:
            si, sh = stack.pop()
            w = i - si
            if w >= min_w and sh >= min_h:
                a = sh * w
                if a > best[0]:
                    best = (a, si, i - 1, sh)
            start = si
        stack.append((start, x))
    return best


def largest_empty_rectangle(chip, *, gap=30.0, cell=40.0, smallest_dut=(120.0, 160.0),
                            region=None):
    """Find the biggest empty axis-aligned box on the die (where to pack more structures).

    Rasterizes the placed structures (inflated by `gap`) onto a `cell`-µm grid and finds the
    largest all-empty rectangle **that can actually hold a `smallest_dut`-sized site** (a thin
    full-width sliver has huge area but holds nothing, so optimizing raw area would make a
    void-fill loop quit on the sliver while site-shaped gaps remain — we optimize *packable* area
    instead). Returns its µm rectangle, area, and how many `smallest_dut` loops fit. Pass
    `region=((x0,y0),(x1,y1))` to search within an explicit area (e.g. the usable die area) instead
    of the component's own bounds — useful for void-filling, where the drawn die boundary would
    otherwise make `chip.bounds()` the full die and the empty top/right strips would be missed if
    the cluster packed into a corner. When NO rectangle can hold a site, returns a zero-size box
    (`fits_smallest_dut == 0`), the loop's stop signal.
    """
    if region is not None:
        (x0, y0), (x1, y1) = region
    else:
        (x0, y0), (x1, y1) = chip.bounds()
    W, H = x1 - x0, y1 - y0
    nx, ny = max(1, int(W / cell) + 1), max(1, int(H / cell) + 1)
    grid = [[0] * nx for _ in range(ny)]
    for r in chip.references:
        (ax0, ay0), (ax1, ay1) = r.bounds()
        ci0 = max(0, int((ax0 - gap - x0) / cell)); ci1 = min(nx - 1, int((ax1 + gap - x0) / cell))
        cj0 = max(0, int((ay0 - gap - y0) / cell)); cj1 = min(ny - 1, int((ay1 + gap - y0) / cell))
        for j in range(cj0, cj1 + 1):
            for i in range(ci0, ci1 + 1):
                grid[j][i] = 1
    # a site needs (site + gap) of clear space to land; require at least that many empty cells
    sw, sh = smallest_dut
    min_w_cells = max(1, int((sw + gap) / cell))
    min_h_cells = max(1, int((sh + gap) / cell))
    heights = [0] * nx
    best = (0, 0, 0, 0, 0)   # area, left, right, bottom_row, height
    for j in range(ny):
        for i in range(nx):
            heights[i] = 0 if grid[j][i] else heights[i] + 1
        a, l, r, h = _max_hist(heights, min_w=min_w_cells, min_h=min_h_cells)
        if a > best[0]:
            best = (a, l, r, j, h)
    _, l, r, jb, h = best
    rx0, rx1 = x0 + l * cell, x0 + (r + 1) * cell
    ry0, ry1 = y0 + (jb - h + 1) * cell, y0 + (jb + 1) * cell
    w_um, h_um = rx1 - rx0, ry1 - ry0
    sw, sh = smallest_dut
    fits = int(w_um / (sw + gap)) * int(h_um / (sh + gap))
    return {
        "x0": round(float(rx0), 1), "y0": round(float(ry0), 1),
        "x1": round(float(rx1), 1), "y1": round(float(ry1), 1),
        "w_um": round(float(w_um), 1), "h_um": round(float(h_um), 1),
        "area_mm2": round(float(w_um * h_um) / 1e6, 3),
        "fits_smallest_dut": int(fits),
    }


# ══════════════════════════════ NEW TOOL 2: LVS ════════════════════════════
def _lvs_one(component):
    """The LVS-guide three checks on one component: connectivity, virtual connections, collisions."""
    nl = component.get_netlist()
    n_conn = len(nl.get("connections", []))
    n_virtual = len(nl.get("virtual connections", []))
    try:
        dangling, _ = _dangling_ports(component)
    except Exception:  # noqa: BLE001
        dangling = -1
    regions, _ = waveguide_collisions(component, "Si")
    n_collisions = len(regions)
    passes = (n_virtual == 0 and dangling == 0 and n_collisions == 0)
    return {"connections": n_conn, "virtual": n_virtual, "dangling_ports": dangling,
            "wg_collisions": n_collisions, "passes": passes}


def lvs(chip):
    """LVS-style sign-off (the lvs_guide.html workflow): every structure's intended connectivity
    is physically realized (no dangling ports), no unresolved virtual connections, and no
    waveguide collisions. Connectivity lives inside each structure, so we check per-structure
    and roll up. Returns {passes, n_fail, per_structure: {name: {...}}}.
    """
    # check ONCE per unique cell (replicates share a cell), then weight by placement count
    cache, counts = {}, {}
    for ref in chip.references:
        nm = ref.component.name
        counts[nm] = counts.get(nm, 0) + 1
        if nm not in cache:
            cache[nm] = _lvs_one(ref.component)
    n_struct = sum(counts.values())
    n_fail = sum(counts[nm] for nm, r in cache.items() if not r["passes"])
    return {"passes": n_fail == 0, "n_structures": n_struct, "n_fail": n_fail,
            "n_unique": len(cache), "per_structure": cache}


# ══════════════════════════════ NEW TOOL 3: raster snapshot + GIF ══════════
import re as _re

# port markers render as red lines; the LiveViewer hides them — strip for clean frames
_PORT_LINE = _re.compile(r"<line[^>]*stroke:#ff0000[^>]*/>")


def _clean_svg(svg_text):
    return _PORT_LINE.sub("", svg_text)


def svg_to_png(svg, png_path, *, width=900, bg="#0d0d0d", scale=2):
    """Rasterize an SVG (string or .svg path) via headless Chromium (Playwright).

    Uses PhotonForge's NATIVE _repr_svg_ rendering (same as the LiveViewer) — no lossy redraw,
    with the red port markers stripped for a clean frame. Returns png_path, or None if
    Playwright/Chromium is unavailable.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:  # noqa: BLE001
        return None
    import pathlib as _pl
    svg_text = svg if "<svg" in svg[:400] else _pl.Path(svg).read_text()
    svg_text = _clean_svg(svg_text)
    html = (f"<!DOCTYPE html><html><head><style>html,body{{margin:0;padding:16px;"
            f"background:{bg}}}svg{{width:{width}px !important;height:auto !important}}</style>"
            f"</head><body>{svg_text}</body></html>")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(device_scale_factor=scale)
            pg.set_content(html)
            el = pg.query_selector("svg")
            el.screenshot(path=str(png_path))
            b.close()
    except Exception:  # noqa: BLE001
        return None
    return png_path


def chip_png(chip, png_path, **kw):
    """Native-quality PNG snapshot of a chip/component (its _repr_svg_ rasterized)."""
    return svg_to_png(chip._repr_svg_(), png_path, **kw)


def _font(name, size):
    """Load a TrueType font at the given pixel size (bare name fails on this box -> use the
    matplotlib-bundled DejaVu; falling back to PIL's tiny default would IGNORE the size)."""
    import os
    from PIL import ImageFont
    try:
        import matplotlib
        p = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    except Exception:  # noqa: BLE001
        pass
    try:
        return ImageFont.truetype(name, size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def _draw_caption(img, lines):
    """Add a large caption BAND ABOVE the image (no overlap with the viewer's own UI).

    First line is the big green title (what's changing); remaining lines are white detail.
    """
    from PIL import Image, ImageDraw
    scale = max(1.0, img.width / 1200.0)
    title_f = _font("DejaVuSans-Bold.ttf", int(31 * scale))
    body_f = _font("DejaVuSans.ttf", int(22 * scale))
    fonts = [title_f] + [body_f] * (len(lines) - 1)
    pad = int(26 * scale)
    gap = int(16 * scale)
    probe = ImageDraw.Draw(img)
    hs = []
    for ln, f in zip(lines, fonts):
        b = probe.textbbox((0, 0), ln, font=f)
        hs.append(b[3] - b[1])
    band = 2 * pad + sum(hs) + gap * (len(lines) - 1)
    out = Image.new("RGB", (img.width, img.height + band), (8, 10, 12))
    out.paste(img, (0, band))
    d = ImageDraw.Draw(out)
    d.line([(0, band - 2), (img.width, band - 2)], fill=(0, 205, 125), width=int(3 * scale))
    y = pad
    for i, (ln, f) in enumerate(zip(lines, fonts)):
        d.text((pad, y), ln, font=f, fill=(0, 235, 140) if i == 0 else (238, 238, 238))
        y += hs[i] + gap
    return out


def make_gif(frame_paths, gif_path, *, fps=1.4, width=900, bg="#0d0d0d", captions=None):
    """Stitch per-step frames into an animated GIF. Frames may be PNG paths or .svg paths.

    SVG frames are rasterized in ONE headless-Chromium session (not relaunched per frame).
    `captions[i]` (a list of text lines) is drawn as a banner under frame i (FOM / journal).
    Returns gif_path, or None if no frames could be rendered.
    """
    import pathlib as _pl
    from PIL import Image
    frame_paths = [str(f) for f in frame_paths]
    raster, tmp = {}, []
    svgs = [(i, f) for i, f in enumerate(frame_paths) if f.endswith(".svg")]
    if svgs:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                b = p.chromium.launch()
                pg = b.new_page(device_scale_factor=2)
                for i, fp in svgs:
                    svg = _clean_svg(_pl.Path(fp).read_text())
                    pg.set_content(f"<!DOCTYPE html><html><head><style>html,body{{margin:0;"
                                   f"padding:16px;background:{bg}}}svg{{width:{width}px !important;"
                                   f"height:auto !important}}</style></head><body>{svg}</body></html>")
                    el = pg.query_selector("svg")
                    if el:
                        out = _pl.Path(gif_path).with_suffix("").as_posix() + f"_f{i:03d}.png"
                        el.screenshot(path=out)
                        raster[i] = out
                        tmp.append(out)
                b.close()
        except Exception:  # noqa: BLE001
            pass
    imgs, caps = [], []
    for i, fp in enumerate(frame_paths):
        path = raster.get(i) if fp.endswith(".svg") else fp
        if path and _pl.Path(path).exists():
            imgs.append(Image.open(path).convert("RGB"))
            caps.append(captions[i] if captions and i < len(captions) else None)
    if not imgs:
        return None
    w = max(im.width for im in imgs)
    h = max(im.height for im in imgs)
    frames = []
    for im, cap in zip(imgs, caps):
        c = Image.new("RGB", (w, h), (13, 13, 13))
        c.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
        if cap:
            c = _draw_caption(c, cap)
        frames.append(c)
    # pad all frames to the tallest (captions may differ in line count)
    fw = max(f.width for f in frames)
    fh = max(f.height for f in frames)
    norm = []
    for f in frames:
        n = Image.new("RGB", (fw, fh), (13, 13, 13))
        n.paste(f, (0, 0))
        norm.append(n)
    norm[0].save(gif_path, save_all=True, append_images=norm[1:],
                 duration=int(1000 / fps), loop=0)
    for t in tmp:
        _pl.Path(t).unlink(missing_ok=True)
    return gif_path


# ══════════════════════════════ discoverability ════════════════════════════
_CATALOG = [
    ("summary(chip, metrics=, meta=, collisions=, drc=, area_tier=)", "reduced-order hierarchical view (JSON)"),
    ("render_text(summary)", "compact text rendering of the summary"),
    ("show_collisions(component, layer)", "EXACT boolean overlap polygons + overlay (LVS style)"),
    ("waveguide_collisions(chip, layer)", "all exact overlap regions, inter + intra structure"),
    ("check_collisions(chip)", "fast gated collision report (inter / wg-cross / heatsink / bondpad)"),
    ("orientation_consistent(chip)", "wafer-prober gate: every site shares one pose (GC+pad direction)"),
    ("run_drc(gds_path)", "KLayout SiEPIC DRC -> per-rule violations + warnings"),
    ("localize_drc(chip, lyrdb)", "map each DRC marker to the structure that owns it"),
    ("paint_violations(chip, collisions, drc_lyrdb=)", "overlay component with violations painted"),
    ("route_length(route_component)", "native physical waveguide length (um)"),
    ("effective_route_length(component=, n_eff=, frequency=)", "native dispersion-aware optical length"),
    ("route_lengths(structure)", "{route_name: length} for one structure"),
    ("tree_view(component)", "native ASCII hierarchy tree"),
    ("netlist(component)", "native connectivity netlist"),
    ("bounds(component_or_reference)", "native bounding box"),
    ("check_all_levels(chip)", "DRC + collisions at chip AND each sub-structure"),
    ("find(chip, name)", "locate a sub-component by name"),
    ("to_view(chip, focus=, show_violations=)", "render one node / overlay for the LiveViewer"),
    ("NAV_JS", "inject via preview_eval -> pfnav.{resetView,zoomIn,moreLevels,layers,...}"),
    ("largest_empty_rectangle(chip)", "biggest free box on the die (room to pack more)"),
    ("lvs(chip)", "LVS verdict: connectivity + virtual connections + collisions, per structure"),
    ("chip_png(chip, png_path)", "native-quality PNG snapshot (Chromium-rasterized _repr_svg_)"),
    ("svg_to_png(svg_or_path, png_path)", "rasterize any SVG via headless Chromium"),
    ("make_gif(frame_paths, gif_path)", "stitch per-step PNG/SVG frames into an animated GIF"),
]


def catalog():
    """Print every tool in the toolbox with a one-line description."""
    print("DoE harness toolbox (import: from tools import toolbox as T):")
    for sig, doc in _CATALOG:
        print(f"  T.{sig:52s} {doc}")


def _main():
    """Self-test: catalog the tools, build a small packed chip from the plan, run the AI tools."""
    import sys, json, pathlib, warnings
    warnings.filterwarnings("ignore", message=".*renamed in the layout.*")
    root = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from tools import components, library, test_structures, floorplan
    catalog()
    components.technology()
    lib = library.default_library()
    plan = json.loads((root / "blackboard" / "doe_plan.json").read_text())
    structs, _ = test_structures.build_from_plan(plan, lib, replicates=3)
    chip, m = floorplan.pack_into_die(structs, die_w=plan["die"]["DIE_W"],
                                      die_h=plan["die"]["DIE_H"], allow_rotation=False)
    print(f"\nbuilt {m['n_placed']} structures on the fixed die (fill {m['fill_fraction']*100:.0f}%)")
    print("orientation:", orientation_consistent(chip).summary())
    print("collisions :", check_collisions(chip).summary())
    print("largest_empty_rectangle:", largest_empty_rectangle(chip))
    v = lvs(chip)
    print(f"lvs: passes={v['passes']}  {v['n_structures']-v['n_fail']}/{v['n_structures']} structures clean")


if __name__ == "__main__":
    _main()
