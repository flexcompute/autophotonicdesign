"""journal.py — Per-iteration archival and time-series logging.

After each simulate.py run the experiment is frozen into
output/experiments/NNNN/ and a row is appended to output/results.tsv. The
agent's reasoning log (journal.md) gets a stub entry that the agent is
expected to fill in before moving on.

Nothing here imports tidy3d; `results` is a plain dict returned by
`design.evaluate`.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

OUTPUT_DIR       = Path("output")
EXPERIMENTS_DIR  = OUTPUT_DIR / "experiments"
RESULTS_TSV      = OUTPUT_DIR / "results.tsv"
JOURNAL_MD       = OUTPUT_DIR / "journal.md"
BEST_DESIGN_PY   = OUTPUT_DIR / "best_design.py"

TSV_COLUMNS = [
    "experiment", "timestamp", "topology", "W_CORE",
    "FOM", "VpiL_Vcm", "C_pF_mm", "loss_dB_cm",
    "wall_time_s", "status", "description",
]


# =========================================================================
# Experiment numbering
# =========================================================================
def next_experiment_number() -> int:
    """Smallest positive integer not yet used as an experiment folder."""
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(
        int(p.name) for p in EXPERIMENTS_DIR.iterdir()
        if p.is_dir() and p.name.isdigit()
    )
    return (existing[-1] + 1) if existing else 1


def experiment_dir(n: int) -> Path:
    return EXPERIMENTS_DIR / f"{n:04d}"


# =========================================================================
# Archiving
# =========================================================================
def archive_run(
    experiment_n: int,
    results: dict,
    status: str = "ok",
    topology: str = "constant",
    description: str = "",
    wall_time_s: float = 0.0,
    extra_files: dict | None = None,
) -> Path:
    """Freeze design.py + outputs into output/experiments/NNNN/.

    Returns the experiment directory path.
    """
    exp_dir = experiment_dir(experiment_n)
    exp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Frozen copy of current design.py
    if Path("design.py").exists():
        shutil.copy2("design.py", exp_dir / "design.py")

    # 2. Frozen copy of the current preview + fields + carriers images
    for fn in ("preview.png", "fields.png", "carriers_at_target.png"):
        src = OUTPUT_DIR / fn
        if src.exists():
            shutil.copy2(src, exp_dir / fn)

    # 3. Any extra files (charge hdf5 pointer, drc.txt, run.log, ...)
    for name, src_path in (extra_files or {}).items():
        src = Path(src_path)
        if src.exists():
            shutil.copy2(src, exp_dir / name)

    # 4. Full structured results.json
    payload = {
        "experiment": experiment_n,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "topology": topology,
        "description": description,
        "status": status,
        "wall_time_s": wall_time_s,
        "results": _jsonable(results),
    }
    (exp_dir / "results.json").write_text(
        json.dumps(payload, indent=2, default=str)
    )

    # 5. Append a row to results.tsv (create header if missing)
    _append_tsv_row(experiment_n, results, payload)

    # 6. Stub-append to journal.md for the agent to fill in
    _append_journal_stub(experiment_n, results, payload)

    return exp_dir


def promote_best(experiment_n: int, results: dict) -> bool:
    """If this experiment is the new highest-FOM, write best_design.py.

    Compares against all OTHER archived experiments so that the first run
    (no prior best) is always promoted, and a repeat of the current best
    FOM is not.

    Returns True when promotion happened.
    """
    import math
    fom = results.get("FOM")
    if fom is None:
        return False
    try:
        fom = float(fom)
        if math.isnan(fom):
            return False
    except (TypeError, ValueError):
        return False

    current_best = _current_best_fom(exclude_experiment=experiment_n)
    if current_best is None or fom > current_best:
        exp_dir = experiment_dir(experiment_n)
        src = exp_dir / "design.py"
        if src.exists():
            shutil.copy2(src, BEST_DESIGN_PY)
        return True
    return False


def revert_to_best() -> bool:
    """Copy best_design.py back over design.py. No-op if best doesn't exist."""
    if BEST_DESIGN_PY.exists():
        shutil.copy2(BEST_DESIGN_PY, "design.py")
        return True
    return False


# =========================================================================
# Internal helpers
# =========================================================================
def _jsonable(obj):
    """Recursively coerce numpy / tidy3d objects to plain json-safe types."""
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    try:
        import numpy as np
        if isinstance(obj, (np.floating, np.integer)):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, complex):
            return [obj.real, obj.imag]
    except Exception:
        pass
    return obj


def _append_tsv_row(n: int, results: dict, payload: dict) -> None:
    RESULTS_TSV.parent.mkdir(parents=True, exist_ok=True)
    new_file = not RESULTS_TSV.exists()
    # Pull W_CORE from the frozen design snapshot. Fallback: try current
    # design.py. If neither available, leave blank.
    w_core = _read_W_CORE(experiment_dir(n) / "design.py") or ""

    row = {
        "experiment": n,
        "timestamp": payload["timestamp"],
        "topology": payload["topology"],
        "W_CORE": w_core,
        "FOM": _fmt(results.get("FOM")),
        "VpiL_Vcm": _fmt(results.get("VpiL_Vcm")),
        "C_pF_mm": _fmt(results.get("C_pF_mm")),
        "loss_dB_cm": _fmt(results.get("loss_dB_cm")),
        "wall_time_s": f"{payload['wall_time_s']:.1f}",
        "status": payload["status"],
        "description": payload["description"].replace("\t", " ").replace("\n", " "),
    }
    with RESULTS_TSV.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t")
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def _append_journal_stub(n: int, results: dict, payload: dict) -> None:
    JOURNAL_MD.parent.mkdir(parents=True, exist_ok=True)
    exists = JOURNAL_MD.exists()
    with JOURNAL_MD.open("a") as f:
        if not exists:
            f.write("# Experiment journal\n\n")
        f.write(f"## Experiment {n} — {payload['topology']}\n\n")
        f.write(f"- **Timestamp**: {payload['timestamp']}\n")
        f.write(f"- **Hypothesis**: _(fill me in)_\n")
        f.write(f"- **Result**: FOM = {results.get('FOM')}, "
                f"VπL = {results.get('VpiL_Vcm')} V·cm, "
                f"C = {results.get('C_pF_mm')} pF/mm, "
                f"loss = {results.get('loss_dB_cm')} dB/cm\n")
        f.write(f"- **Status**: {payload['status']}\n")
        f.write(f"- **Kept or discarded**: _(fill me in)_\n")
        f.write(f"- **Lesson**: _(fill me in)_\n\n")


def _fmt(x) -> str:
    if x is None:
        return ""
    try:
        import math
        if math.isnan(float(x)):
            return ""
    except Exception:
        pass
    try:
        return f"{float(x):.5g}"
    except Exception:
        return str(x)


def _current_best_fom(exclude_experiment: int | None = None) -> float | None:
    if not RESULTS_TSV.exists():
        return None
    best = None
    with RESULTS_TSV.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            try:
                if exclude_experiment is not None and int(row["experiment"]) == exclude_experiment:
                    continue
                fom = float(row["FOM"])
            except Exception:
                continue
            if best is None or fom > best:
                best = fom
    return best


def _read_W_CORE(design_py: Path) -> str | None:
    """Cheap regex read of W_CORE from a design.py snapshot."""
    if not design_py.exists():
        return None
    import re
    for line in design_py.read_text().splitlines():
        m = re.match(r"\s*W_CORE\s*=\s*([0-9.eE+-]+)", line)
        if m:
            return m.group(1)
    return None


def load_all_results() -> list[dict]:
    """Read back every row of results.tsv as a list of dicts (strings)."""
    if not RESULTS_TSV.exists():
        return []
    with RESULTS_TSV.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))
