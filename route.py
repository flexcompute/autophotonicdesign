"""
route.py — Run one routing experiment with the strategy in design.py.

Loads the projector circuit, applies design.MODE + design.CONFIG, scores
the resulting layout against the DRC criteria, and prints a results block
the agent can grep.

Usage:
    python route.py
    python route.py --description "BFS grid p25, M1 obstacles on"

Exit codes:
    0  success (regardless of pass/fail)
    1  exception during build / run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback


# Add tools/ to sys.path before anything that imports routing modules.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--description", default="",
                        help="Free-text note to log in results.tsv.")
    parser.add_argument("--no-archive", action="store_true",
                        help="Skip writing output/experiments/NNNN/ archive.")
    args = parser.parse_args()

    start = time.perf_counter()
    # projector_circuit_setup chdir's into tools/ during import. To keep
    # output/, design.py, etc. resolvable, all paths in this module are
    # rooted at HERE rather than cwd.
    os.makedirs(os.path.join(HERE, "output"), exist_ok=True)

    try:
        from runners import run_manhattan, run_grid
        import design

        mode = design.get_mode()
        cfg = design.get_config()

        print("=== Routing experiment ===")
        print(design.snapshot_header())
        print(f"# description: {args.description!r}")

        if mode == "manhattan_indep":
            metrics = run_manhattan(cfg, mode="indep")
        elif mode == "manhattan_seq":
            metrics = run_manhattan(cfg, mode="seq")
        elif mode == "grid":
            metrics = run_grid(cfg)
        else:
            print(f"ERROR: unknown MODE {mode!r} (expected manhattan_indep, "
                  "manhattan_seq, or grid)")
            return 1

    except Exception as exc:
        traceback.print_exc()
        elapsed = time.perf_counter() - start
        print("CRASH")
        print(f"wall_time_s: {elapsed:.1f}")
        return 1

    elapsed = time.perf_counter() - start

    passes = (metrics["routed"] == metrics["n_total"] and
              metrics["heater"] == 0 and metrics["rr"] == 0 and metrics["pp"] == 0)
    score = ((metrics["n_total"] - metrics["routed"]) * 100 +
             max(metrics["heater"], 0) * 10 +
             max(metrics["rr"], 0) * 10 +
             max(metrics["pp"], 0) * 5)

    print("\n=== Results ===")
    print(f"metric_score: {score}")
    print(f"routed: {metrics['routed']}")
    print(f"n_total: {metrics['n_total']}")
    print(f"heater_violations: {metrics['heater']}")
    print(f"route_route_violations: {metrics['rr']}")
    print(f"pad_pad_violations: {metrics['pp']}")
    print(f"passes_drc: {int(passes)}")
    print(f"wall_time_s: {elapsed:.1f}")

    if not args.no_archive:
        _archive(metrics, score, passes, elapsed, args.description)

    return 0


def _archive(metrics, score, passes, elapsed, description):
    """Write output/experiments/NNNN/{result.json,design.py} and update results.tsv."""
    base = os.path.join(HERE, "output", "experiments")
    os.makedirs(base, exist_ok=True)
    existing = [d for d in os.listdir(base) if d.isdigit()] if os.path.isdir(base) else []
    n = max([int(d) for d in existing], default=0) + 1
    out = os.path.join(base, f"{n:04d}")
    os.makedirs(out, exist_ok=True)

    import shutil
    shutil.copy(os.path.join(HERE, "design.py"), os.path.join(out, "design.py"))

    record = dict(
        n=n, description=description,
        score=score, passes=passes, wall_time_s=elapsed,
        metrics={k: v for k, v in metrics.items() if k != "log"},
    )
    with open(os.path.join(out, "result.json"), "w") as f:
        json.dump(record, f, indent=2)

    tsv = os.path.join(HERE, "output", "results.tsv")
    new = not os.path.exists(tsv)
    with open(tsv, "a") as f:
        if new:
            f.write("experiment\tscore\tpasses\twall_time_s\trouted\theater\trr\tpp\tdescription\n")
        f.write(
            f"{n}\t{score}\t{int(passes)}\t{elapsed:.1f}\t"
            f"{metrics['routed']}/{metrics['n_total']}\t{metrics['heater']}\t"
            f"{metrics['rr']}\t{metrics['pp']}\t{description}\n"
        )

    print(f"\nArchived -> {out}")
    print(f"  score={score}  passes={passes}")


if __name__ == "__main__":
    sys.exit(main())
