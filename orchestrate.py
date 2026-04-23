"""
orchestrate.py — Deterministic bookkeeping for the auto-design loop.

DO NOT MODIFY. The agent should only modify design.py.

Subcommands:
    init
        Create output/ tree, results.tsv header, empty journal.md.
        Idempotent — safe to run at any time.

    log N --hypothesis "..." --lesson "..." [--title "..."]
        Post-simulation bookkeeping. Parses output/run.log, appends a row
        to output/results.tsv, appends an entry to output/journal.md,
        compares metric against output/best_metric.txt, and either
        snapshots design.py as the new best or reverts it from the
        existing best. Prints a one-line verdict.

Usage:
    python orchestrate.py init
    python orchestrate.py log 12 \\
        --hypothesis "Lengthen taper from 5 to 7 um to reduce scattering" \\
        --lesson    "Scattering dropped; transmission +1.8 percentage points"
"""

import argparse
import re
import shutil
from pathlib import Path

OUTPUT = Path("output")
RUN_LOG = OUTPUT / "run.log"
RESULTS_TSV = OUTPUT / "results.tsv"
JOURNAL_MD = OUTPUT / "journal.md"
BEST_DESIGN = OUTPUT / "best_design.py"
BEST_METRIC = OUTPUT / "best_metric.txt"
DESIGN = Path("design.py")

TSV_HEADER = "experiment\tmetric\twall_time_s\tstatus\tdescription\n"
JOURNAL_HEADER = "# Experiment Journal\n\n"

# Matches "key: numeric_value" lines from simulate.py's Results section.
NUM_LINE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$"
)


def cmd_init(_args):
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "previews").mkdir(exist_ok=True)
    if not RESULTS_TSV.exists():
        RESULTS_TSV.write_text(TSV_HEADER, encoding="utf-8")
        print(f"Created {RESULTS_TSV}")
    if not JOURNAL_MD.exists():
        JOURNAL_MD.write_text(JOURNAL_HEADER, encoding="utf-8")
        print(f"Created {JOURNAL_MD}")
    print("init ok")


def parse_run_log(path: Path):
    """Return (metric, wall_time, crashed) from the latest simulate.py run.

    The primary metric is the first "<key>: <number>" line inside the
    `=== Results ===` block (handles both scalar and dict returns from
    evaluate()). wall_time comes from the "wall_time_s:" line.
    """
    if not path.exists():
        return None, None, True
    text = path.read_text(encoding="utf-8", errors="replace")
    crashed = "CRASH" in text

    idx = text.rfind("=== Results ===")
    section = text[idx:] if idx != -1 else ""

    metric = None
    wall_time = None
    for line in section.splitlines():
        m = NUM_LINE.match(line.strip())
        if not m:
            continue
        key, val = m.group(1), float(m.group(2))
        if key == "wall_time_s":
            wall_time = val
        elif metric is None:
            metric = val

    if metric is None:
        crashed = True
    return metric, wall_time, crashed


def read_best_metric():
    if not BEST_METRIC.exists():
        return None
    try:
        return float(BEST_METRIC.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def append_tsv(n, metric, wall_time, status, description):
    if not RESULTS_TSV.exists():
        RESULTS_TSV.write_text(TSV_HEADER, encoding="utf-8")
    metric_s = f"{metric:.6f}" if metric is not None else "NA"
    wt_s = f"{wall_time:.1f}" if wall_time is not None else "NA"
    safe_desc = description.replace("\t", " ").replace("\n", " ")
    with RESULTS_TSV.open("a", encoding="utf-8") as f:
        f.write(f"{n}\t{metric_s}\t{wt_s}\t{status}\t{safe_desc}\n")


def append_journal(n, title, hypothesis, metric, prev_best, status, lesson):
    if not JOURNAL_MD.exists():
        JOURNAL_MD.write_text(JOURNAL_HEADER, encoding="utf-8")

    if metric is None:
        metric_s = "CRASH (no metric)"
        delta_s = "n/a"
    else:
        metric_s = f"{metric:.4f}"
        if prev_best is None:
            delta_s = "n/a (first experiment)"
        else:
            delta = metric - prev_best
            direction = "improved" if delta > 0 else ("equal" if delta == 0 else "worse")
            delta_s = f"{delta:+.4f} ({direction})"

    entry = (
        f"\n## Experiment {n} — {title}\n\n"
        f"- **Hypothesis:** {hypothesis}\n"
        f"- **Result:** metric = {metric_s}\n"
        f"- **vs. previous best:** {delta_s}\n"
        f"- **Kept or discarded:** {status}\n"
        f"- **Lesson learned:** {lesson}\n"
    )
    with JOURNAL_MD.open("a", encoding="utf-8") as f:
        f.write(entry)


def cmd_log(args):
    n = args.experiment
    hypothesis = args.hypothesis
    lesson = args.lesson
    title = args.title or (hypothesis[:60] + ("..." if len(hypothesis) > 60 else ""))

    metric, wall_time, crashed = parse_run_log(RUN_LOG)
    prev_best = read_best_metric()

    if crashed:
        status = "CRASH"
    elif prev_best is None:
        status = "KEPT"  # first successful experiment establishes baseline
    elif metric > prev_best:
        status = "KEPT"
    else:
        status = "DISCARDED"

    if status == "KEPT":
        shutil.copy(DESIGN, BEST_DESIGN)
        BEST_METRIC.write_text(f"{metric}\n", encoding="utf-8")
    else:
        if BEST_DESIGN.exists():
            shutil.copy(BEST_DESIGN, DESIGN)

    append_tsv(n, metric, wall_time, status, hypothesis)
    append_journal(n, title, hypothesis, metric, prev_best, status, lesson)

    if status == "CRASH":
        reverted = " (reverted to best_design.py)" if BEST_DESIGN.exists() else ""
        print(f"Experiment {n}: CRASH{reverted}")
    else:
        prev_s = f"{prev_best:.4f}" if prev_best is not None else "n/a"
        print(f"Experiment {n}: metric={metric:.4f}, prev best={prev_s} -> {status}")


def main():
    p = argparse.ArgumentParser(
        description="Deterministic bookkeeping for the auto-design loop."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Initialize output/ tree and state files.")

    lp = sub.add_parser("log", help="Log a completed experiment and decide keep/discard.")
    lp.add_argument("experiment", type=int, help="Experiment number (1, 2, 3, ...)")
    lp.add_argument("--hypothesis", required=True, help="One-line description of what changed and why.")
    lp.add_argument("--lesson", required=True, help="One-line lesson learned from this experiment.")
    lp.add_argument("--title", default=None, help="Short journal title (default: truncated hypothesis).")

    args = p.parse_args()
    {"init": cmd_init, "log": cmd_log}[args.cmd](args)


if __name__ == "__main__":
    main()
