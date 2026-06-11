"""
Validation for the DoE chip. Two independent layers, both used as hard gates:

  1. KLayout DRC  — the real SiEPIC_EBeam.drc foundry deck (min width/space, layer overlaps,
     boundary/floorplan, ...). Authoritative but needs the KLayout app. Run via subprocess
     (the tidy3d DRCRunner wrapper cannot locate KLayout.app on macOS), parsed with DRCResults.

  2. Geometric collision checks — pf.boolean-based, no external tools, always available. Catches
     the things that motivated this module: waveguides curling/crossing and layers overlapping.
     Uses the "sum(individual areas) - union area" trick: abutting port joints contribute ~0
     overlap, genuine crossings/overlaps contribute real area. Cheap (one union per layer).

Design note: KLayout DRC is the authority when available; the geometric checks are the always-on
floor and give the agent a fast, interpretable crossing signal between full DRC runs.
"""
import os
import shutil
import subprocess
import pathlib
from dataclasses import dataclass, field

import photonforge as pf

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNSET = REPO_ROOT / "SiEPIC_EBeam.drc"

# layers we collision-check (name -> meaning)
WG = "Si"
M1 = "M1_heater"
M2 = "M2_router"
MOPEN = "M_Open"

# DRC rule classification. Boundary is handled via a FloorPlan layer in floorplan.py; Devices is
# a functional DevRec-overlap note. SiEPIC-1a etc. are deck-labelled "Warning:" rules (here, a
# sub-micron PinRec sliver where a route meets the reused dual-ring PDK cell) — surfaced, not gated.
_DRC_INFO_ONLY = {"Boundary", "Devices"}
_DRC_WARNINGS = {"SiEPIC-1a", "SiEPIC-1b", "SiEPIC-2", "SiEPIC-3"}


# ───────────────────────────── geometry helpers ─────────────────────────────
def _gds(layer):
    t = pf.config.default_technology
    return t.layers[layer].layer if layer in t.layers else layer


def layer_polygons(comp, layer):
    """Flattened polygons on `layer` (global coords), via get_structures (non-mutating)."""
    structs = comp.get_structures(depth=-1)
    if isinstance(structs, dict):
        return structs.get(layer, []) or structs.get(_gds(layer), [])
    return [s for s in structs if getattr(s, "layer", None) in (layer, _gds(layer))]


def _area(polys):
    return sum(abs(p.area()) for p in polys) if polys else 0.0


def _union_area(polys):
    return _area(pf.boolean(polys, [], "+")) if polys else 0.0


def overlap_area(comp, layer):
    """Unintended self-overlap on a layer = sum(individual) - union. ~0 for clean layouts."""
    polys = layer_polygons(comp, layer)
    if len(polys) < 2:
        return 0.0
    ov = _area(polys) - _union_area(polys)
    return ov if ov > 1e-3 else 0.0


# ───────────────────────────── collision report ─────────────────────────────
BONDPAD_MIN_PITCH = 150.0   # um, probe / wire-bond spacing


@dataclass
class CollisionReport:
    # Gated signals:
    inter_structure_um2: float      # geometry of DIFFERENT placed structures overlapping (packing too tight)
    wg_crossing_um2: float          # within-structure waveguide self-overlap (routes crossing, e.g. bad loop)
    m2_over_m1_um2: float           # M2 over M1 heater outside M_Open contacts (heatsink rule)
    bondpad_violations: int = 0     # pairs of bond pads closer than the required pitch
    bondpad_min_pitch_um: float = None  # closest pad-pad center distance on the chip
    # Detail:
    inter_by_layer: dict = field(default_factory=dict)        # {layer: um2}
    wg_crossing_by_structure: dict = field(default_factory=dict)  # {structure_name: um2}
    bondpad_close_pairs: list = field(default_factory=list)   # [(centerA, centerB, dist), ...]

    @property
    def clean(self):
        return (self.inter_structure_um2 < 1e-2 and self.wg_crossing_um2 < 1e-2
                and self.m2_over_m1_um2 < 1e-2 and self.bondpad_violations == 0)

    def summary(self):
        flag = "clean" if self.clean else "COLLISIONS"
        x = []
        if self.inter_structure_um2 >= 1e-2:
            x.append(f"inter-structure={self.inter_structure_um2:.2f}um2 {self.inter_by_layer}")
        if self.wg_crossing_um2 >= 1e-2:
            x.append(f"WG-cross={self.wg_crossing_um2:.2f}um2 in {list(self.wg_crossing_by_structure)}")
        if self.m2_over_m1_um2 >= 1e-2:
            x.append(f"M2/M1-heatsink={self.m2_over_m1_um2:.2f}um2")
        if self.bondpad_violations:
            x.append(f"bondpad-pitch<{BONDPAD_MIN_PITCH:.0f}um x{self.bondpad_violations} "
                     f"(min {self.bondpad_min_pitch_um}um)")
        return f"collisions[{flag}] " + (" ".join(x) if x else "none")


def m2_over_m1(chip):
    """M2 area crossing M1, excluding intended M_Open via contacts (heatsink rule)."""
    m1 = layer_polygons(chip, M1)
    m2 = layer_polygons(chip, M2)
    if not m1 or not m2:
        return 0.0
    inter = pf.boolean(m1, m2, "*")
    if not inter:
        return 0.0
    opens = layer_polygons(chip, MOPEN)
    if opens:
        inter = pf.boolean(inter, opens, "-")
    a = _area(inter)
    return a if a > 1e-3 else 0.0


def bondpad_centers(chip):
    """Global centers of every bond pad, grouped by parent structure.

    Returns {structure_name: [(x, y), ...]}. Packing is translation-only, so composing reference
    origins gives global coordinates.
    """
    by_struct = {}
    for s in chip.references:
        sx, sy = float(s.origin[0]), float(s.origin[1])
        pads = [(sx + float(p.origin[0]), sy + float(p.origin[1]))
                for p in s.component.references if p.component.name.startswith("BondPad")]
        if pads:
            by_struct[s.component.name] = pads
    return by_struct


def bondpad_spacing(chip, *, min_pitch=BONDPAD_MIN_PITCH):
    """Bond pads within ONE structure must be >= min_pitch apart (single probe-card touchdown,
    127/150 um needle pitch). Cross-structure pad overlap is caught by the inter-structure gate;
    cross-structure probe clearance is the packing gap's job, not this rule.
    """
    by_struct = bondpad_centers(chip)
    close, min_d = [], None
    for name, pads in by_struct.items():
        for i in range(len(pads)):
            for j in range(i + 1, len(pads)):
                d = ((pads[i][0] - pads[j][0]) ** 2 + (pads[i][1] - pads[j][1]) ** 2) ** 0.5
                min_d = d if min_d is None else min(min_d, d)
                if d < min_pitch - 1e-6:
                    close.append((name, pads[i], pads[j], round(d, 1)))
    return close, (round(min_d, 1) if min_d is not None else None)


def collision_regions(component, layer, *, min_area=1e-3):
    """Exact overlap POLYGONS on `layer`, the LVS-guide show_collisions() way.

    Pairwise pf.boolean(..., "*") between the component's references (and top-level geometry) on
    the given layer. Clean abutting connections share only an edge -> empty intersection; a real
    overlap (crossing/too-close waveguides) -> real-area polygons. Works at ANY level: pass the
    chip (refs = structures -> inter-structure overlaps) or one structure (refs = GC/route/DUT ->
    intra-structure waveguide crossings).
    """
    refs = component.references
    try:
        main = component.get_structures(layer, depth=0)
    except TypeError:
        main = []
    regions = []
    structs = []
    for r in refs:
        try:
            structs.append(r.get_structures(layer))
        except TypeError:
            structs.append([])
    for i, s0 in enumerate(structs):
        if main and s0:
            regions += [p for p in pf.boolean(main, s0, "*") if abs(p.area()) > min_area]
        for j in range(i + 1, len(structs)):
            if s0 and structs[j]:
                regions += [p for p in pf.boolean(structs[j], s0, "*") if abs(p.area()) > min_area]
    return regions


def waveguide_collisions(chip, layer=WG, *, include_intra=True):
    """All exact overlap polygons on a routing layer: inter-structure + (optional) intra-structure.

    Returns (regions, by_structure) where by_structure maps a structure name -> its own internal
    crossing polygons. This is the authoritative "where do waveguides collide" map.
    """
    regions = list(collision_regions(chip, layer))      # inter-structure
    by_structure = {}
    if include_intra:
        for ref in chip.references:
            intra = collision_regions(ref.component, layer)
            if intra:
                by_structure[ref.component.name] = intra
                # shift intra regions into chip coordinates for painting
                ox, oy = float(ref.origin[0]), float(ref.origin[1])
                regions += [p.copy().translate((ox, oy)) for p in intra]
    return regions, by_structure


def collision_map(component, layer=WG):
    """LVS-style overlay: a copy of `component` with exact overlaps painted on VIOLATION. Renderable."""
    from . import violations as _vio
    _vio.ensure_layer()
    result = pf.Component(f"{component.name}_collisions")
    result.add_reference(component)
    regions, _ = waveguide_collisions(component, layer)
    for p in regions:
        result.add(_vio.VIO, p)
    return result, len(regions)


def check_collisions(chip, *, wg_cross_threshold=0.05, bondpad_min_pitch=BONDPAD_MIN_PITCH):
    """Geometric collision report for a packed chip.

    Two unambiguous signals (self-overlap WITHIN one structure on M1/M2 is intended — bar,
    leads, contacts and route+pad merge into one electrode/net — so it is NOT a collision):
      * inter-structure overlap: total flattened overlap on a layer minus the sum of each
        structure's own (intended) self-overlap = geometry of different structures touching.
      * wg crossing: ROUTING-induced Si overlap within one structure, measured PAIRWISE between
        the structure's references (GCs / routes / DUT). A device whose DUT contains an INTENDED
        waveguide crossing (the `crossing` test element) keeps that crossing inside one reference,
        so it is correctly NOT flagged; a route that curls back and crosses another route or the
        DUT spans two references and IS flagged. (Using whole-component sum-minus-union would
        wrongly count the crossing element's intended geometry as a collision.)
    """
    refs = chip.references
    # intra-structure waveguide crossings: compute ONCE per unique cell (replicates share a cell)
    wg_by_struct, _seen = {}, {}
    for ref in refs:
        nm = ref.component.name
        if nm not in _seen:
            regions = collision_regions(ref.component, WG)
            _seen[nm] = sum(abs(p.area()) for p in regions)
        if _seen[nm] >= wg_cross_threshold:
            wg_by_struct[nm] = round(_seen[nm], 3)
    # inter-structure overlap: pack guarantees a gap, so bbox-prefilter and run the exact boolean
    # ONLY on the rare overlapping pairs. (Avoids a chip-level union over all ~N*100 polygons,
    # which was the O(structures) bottleneck.)
    bbs = [r.bounds() for r in refs]

    def _bbox_overlap(a, b):
        (ax0, ay0), (ax1, ay1) = a
        (bx0, by0), (bx1, by1) = b
        return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)

    inter_area = 0.0
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            if _bbox_overlap(bbs[i], bbs[j]):
                for lyr in (WG, M2):
                    si = refs[i].get_structures(lyr)
                    sj = refs[j].get_structures(lyr)
                    if si and sj:
                        inter_area += sum(abs(p.area()) for p in pf.boolean(si, sj, "*"))
    close_pads, min_pitch = bondpad_spacing(chip, min_pitch=bondpad_min_pitch)
    return CollisionReport(
        inter_structure_um2=round(inter_area, 3),
        wg_crossing_um2=round(sum(wg_by_struct.values()), 3),
        m2_over_m1_um2=round(m2_over_m1(chip), 3),
        bondpad_violations=len(close_pads),
        bondpad_min_pitch_um=min_pitch,
        inter_by_layer={"inter": round(inter_area, 3)} if inter_area >= 1e-2 else {},
        wg_crossing_by_structure=wg_by_struct,
        bondpad_close_pairs=close_pads,
    )


# ───────────────────────── orientation (wafer-prober same-direction) ─────────────────────────
@dataclass
class OrientationReport:
    """Every placed site must share ONE orientation so the wafer prober's fiber array + probe
    card land the same way at every measurement site. Packing is translation-only, so any
    rotation/reflection of a reference would break this — that is exactly what this gate catches.
    """
    consistent: bool
    n_distinct: int                          # number of distinct (rotation, x_reflection) poses
    poses: dict = field(default_factory=dict)     # {(rotation, x_reflection): count}
    offenders: list = field(default_factory=list)  # structure names not in the majority pose

    def summary(self):
        flag = "uniform" if self.consistent else "MIXED"
        body = " ".join(f"rot{int(r)}{'/refl' if x else ''}x{n}" for (r, x), n in self.poses.items())
        extra = f"  offenders={self.offenders[:6]}" if self.offenders else ""
        return f"orientation[{flag}] {self.n_distinct} pose(s): {body}{extra}"


def orientation_consistent(chip):
    """Check every placed reference shares one pose (same rotation, no/ same reflection).

    With `allow_rotation=False` packing this is guaranteed; the gate makes the wafer-prober
    constraint explicit and catches any regression (a device built facing the wrong way, or a
    future allow_rotation=True). Returns an OrientationReport.
    """
    poses = {}
    pose_of = {}
    for r in chip.references:
        key = (round(float(r.rotation), 3), bool(r.x_reflection))
        poses[key] = poses.get(key, 0) + 1
        pose_of.setdefault(key, []).append(r.component.name)
    if not poses:
        return OrientationReport(consistent=True, n_distinct=0)
    majority = max(poses, key=poses.get)
    offenders = sorted({nm for k, names in pose_of.items() if k != majority for nm in names})
    return OrientationReport(consistent=(len(poses) == 1), n_distinct=len(poses),
                             poses=poses, offenders=offenders)


# ───────────────────────────── KLayout DRC ─────────────────────────────
def _find_klayout():
    for cand in (os.environ.get("KLAYOUT_BIN"), "klayout",
                 "/Applications/klayout.app/Contents/MacOS/klayout",
                 "/Applications/KLayout/klayout.app/Contents/MacOS/klayout"):
        if not cand:
            continue
        p = shutil.which(cand) or (cand if os.path.exists(cand) else None)
        if p:
            return p
    return None


@dataclass
class DRCReport:
    available: bool
    is_clean: bool = True
    counts: dict = field(default_factory=dict)      # {rule: n} HARD violations (gate the FOM)
    warnings: dict = field(default_factory=dict)    # {rule: n} deck "Warning:" rules (reported)
    info_only: dict = field(default_factory=dict)   # {rule: n} boundary/device noise
    error: str = ""

    @property
    def total_actionable(self):
        return sum(self.counts.values())

    @property
    def passes(self):
        """Gate signal: KLayout absent => not gating on DRC; else no HARD violations."""
        return (not self.available) or (self.total_actionable == 0)

    def summary(self):
        if not self.available:
            return f"DRC[skipped: {self.error or 'KLayout not found'}]"
        flag = "clean" if not self.total_actionable else "VIOLATIONS"
        body = " ".join(f"{k}={v}" for k, v in sorted(self.counts.items(), key=lambda x: -x[1]))
        extra = ""
        if self.warnings:
            extra += "  warn:" + " ".join(f"{k}={v}" for k, v in self.warnings.items())
        if self.info_only:
            extra += "  info:" + " ".join(f"{k}={v}" for k, v in self.info_only.items())
        return f"DRC[{flag}] {body or 'none'}{extra}"


def klayout_drc(gds_path, *, runset=RUNSET, resultsfile=None, timeout=180):
    """Run the SiEPIC KLayout DRC deck on `gds_path`. Gracefully skips if KLayout is absent."""
    klayout = _find_klayout()
    if klayout is None:
        return DRCReport(available=False, error="KLayout not found (set KLAYOUT_BIN)")
    if not pathlib.Path(runset).exists():
        return DRCReport(available=False, error=f"runset missing: {runset}")
    gds_path = str(pathlib.Path(gds_path).resolve())
    resultsfile = str(pathlib.Path(resultsfile or (pathlib.Path(gds_path).parent / "drc_results.lyrdb")).resolve())
    try:
        subprocess.run(
            [klayout, "-b", "-r", str(runset),
             "-rd", f"gdsfile={gds_path}", "-rd", f"resultsfile={resultsfile}"],
            check=True, capture_output=True, timeout=timeout,
        )
    except Exception as e:  # noqa: BLE001 - report any failure, never crash the loop
        return DRCReport(available=False, error=f"klayout run failed: {e}")

    try:
        from tidy3d.plugins.klayout.drc import DRCResults
        res = DRCResults.load(resultsfile)
    except Exception as e:  # noqa: BLE001
        return DRCReport(available=False, error=f"results parse failed: {e}")

    counts, warnings, info = {}, {}, {}
    for rule, n in res.violation_counts.items():
        if not n:
            continue
        bucket = info if rule in _DRC_INFO_ONLY else (warnings if rule in _DRC_WARNINGS else counts)
        bucket[rule] = int(n)
    return DRCReport(available=True, is_clean=res.is_clean,
                     counts=counts, warnings=warnings, info_only=info)
