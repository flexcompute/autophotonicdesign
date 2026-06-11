"""
Hierarchy traversal + multi-level validation.

The agent uses this to traverse the component tree (chip -> test structures -> DUT / GC / pad /
route) and run DRC + collision checks at ANY level: the full chip, or a single sub-component to
localize a problem. Sub-component DRC works because KLayout DRC runs on any GDS and the collision
checks run on any Component.

CLI:  python -m tools.hierarchy          # tree + DRC at chip and per-structure level (live DoE)
      python -m tools.hierarchy <name>   # DRC just the named sub-component
"""
import sys
import pathlib
import tempfile

import photonforge as pf

from . import validation as V


def tree(comp, max_depth=4):
    """Nested dict of the hierarchy: name, bbox (w,h), child count, recursing into references."""
    (x0, y0), (x1, y1) = comp.bounds()
    node = {"name": comp.name, "w": round(float(x1 - x0), 1), "h": round(float(y1 - y0), 1),
            "children": []}
    if max_depth > 0:
        seen = {}
        for ref in comp.references:
            seen[ref.component.name] = seen.get(ref.component.name, 0) + 1
        done = set()
        for ref in comp.references:
            nm = ref.component.name
            if nm in done:
                continue
            done.add(nm)
            child = tree(ref.component, max_depth - 1)
            child["count"] = seen[nm]
            node["children"].append(child)
    return node


def tree_text(comp, max_depth=4, _indent=0):
    node = tree(comp, max_depth) if _indent == 0 else comp
    lines = []

    def rec(n, d):
        c = f" x{n['count']}" if n.get("count", 1) > 1 else ""
        lines.append("  " * d + f"{n['name']}{c}  [{n['w']:.0f}x{n['h']:.0f}um]")
        for ch in n["children"]:
            rec(ch, d + 1)
    rec(node, 0)
    return "\n".join(lines)


def find(comp, name, _depth=6):
    """Find the first sub-component whose name contains `name` (case-insensitive)."""
    if name.lower() in comp.name.lower():
        return comp
    if _depth <= 0:
        return None
    for ref in comp.references:
        hit = find(ref.component, name, _depth - 1)
        if hit is not None:
            return hit
    return None


def validate_node(comp, *, run_drc=True, label=None):
    """Run collision + (optionally) KLayout DRC on ANY component (chip or sub-component)."""
    label = label or comp.name
    collisions = V.check_collisions(comp) if comp.references else None
    drc = None
    if run_drc:
        with tempfile.NamedTemporaryFile(suffix=".gds", delete=False) as f:
            gds = f.name
        comp.write_gds(gds)
        drc = V.klayout_drc(gds)
        pathlib.Path(gds).unlink(missing_ok=True)
    return {"label": label, "collisions": collisions, "drc": drc}


def check_all_levels(chip, *, run_drc=True, per_structure=True):
    """DRC + collisions at the full-chip level AND each top-level structure."""
    results = [validate_node(chip, run_drc=run_drc, label="CHIP")]
    if per_structure:
        for ref in chip.references:
            results.append(validate_node(ref.component, run_drc=run_drc))
    return results


def _print_result(r):
    line = f"  {r['label']:30s}"
    if r["collisions"] is not None:
        line += " " + r["collisions"].summary()
    if r["drc"] is not None:
        line += " | " + r["drc"].summary()
    print(line)


def main():
    import warnings
    warnings.filterwarnings("ignore", message=".*renamed in the layout.*")
    ROOT = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT))
    from run import build_chip
    import design
    chip, _, _ = build_chip(design)

    if len(sys.argv) > 1:
        node = find(chip, sys.argv[1])
        if node is None:
            print(f"no sub-component matching '{sys.argv[1]}'")
            return
        print(f"DRC/collisions for sub-component: {node.name}")
        _print_result(validate_node(node))
        return

    print("HIERARCHY (native pf tree_view):")
    print(chip.tree_view())
    print("\nHIERARCHY (with bounding boxes):")
    print(tree_text(chip, max_depth=2))
    print("\nMULTI-LEVEL VALIDATION (chip + each structure):")
    for r in check_all_levels(chip, run_drc=True):
        _print_result(r)


if __name__ == "__main__":
    main()
