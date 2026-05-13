"""
drc.py — Pre-flight DRC check.

Lightweight: runs the same routing strategy that route.py would but
reports only the violation summary (no archive, no record). Use this to
confirm an idea before paying for the full route.py run.

Usage:
    python drc.py

Exits 0 on PASS, 1 if any violation is present.
"""
from __future__ import annotations

import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))


def main():
    from runners import run_manhattan, run_grid
    import design

    mode = design.get_mode()
    cfg = design.get_config()

    print(f"DRC check  ·  MODE={mode}  ALGORITHM={cfg['ALGORITHM']}")
    if mode == "manhattan_indep":
        m = run_manhattan(cfg, mode="indep")
    elif mode == "manhattan_seq":
        m = run_manhattan(cfg, mode="seq")
    elif mode == "grid":
        m = run_grid(cfg)
    else:
        print(f"DRC ERROR: unknown MODE {mode!r}")
        return 1

    print(f"  routed             : {m['routed']}/{m['n_total']}")
    print(f"  heater crossings   : {m['heater']}")
    print(f"  route × route      : {m['rr']}")
    print(f"  pad × pad          : {m['pp']}")

    passes = (m["routed"] == m["n_total"] and
              m["heater"] == 0 and m["rr"] == 0 and m["pp"] == 0)
    if passes:
        print("DRC PASSED")
        return 0
    print("DRC FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
