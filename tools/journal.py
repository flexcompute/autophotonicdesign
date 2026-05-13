"""journal.py — Per-iteration archival and time-series logging for the RF agent.

After each `simulate.py` run the experiment is frozen into
output/experiments/NNNN/ and a row is appended to output/results.tsv. The
agent's reasoning log (journal.md) gets a stub entry that the agent is
expected to fill in before moving on.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

OUTPUT_DIR      = Path("output")
EXPERIMENTS_DIR = OUTPUT_DIR / "experiments"
RESULTS_TSV     = OUTPUT_DIR / "results.tsv"
JOURNAL_MD      = OUTPUT_DIR / "journal.md"
BEST_DESIGN_PY  = OUTPUT_DIR / "best_design.py"

# Order of agent-tunable scalars to snapshot into the TSV.
SNAPSHOT_KEYS = [
    "T_S", "T_R", "T_H", "T_T", "T_C",
    "G", "WS", "WG", "TM", "TSIO21",
    "N_PERIODS",
    # Topology extras (mostly zero unless that topology is active)
    "T_R_SIG", "T_R_GND",
    "SLOT_W", "SLOT_GAP",
    "CAP_W", "CAP_OVERHANG",
    "U_PERIOD_RATIO", "U_W", "U_REACH",
]

TSV_COLUMNS = [
    "experiment", "timestamp", "topology",
    "FOM", "alpha_0_dBcm_per_sqrtGHz",
    "alpha_at_Fref_dBcm", "Z0_real_at_Fref", "n_eff_at_Fref",
    "R_Ohm_per_mm_at_Fref", "L_nH_per_mm_at_Fref",
    "G_S_per_mm_at_Fref", "C_pF_per_mm_at_Fref",
    *SNAPSHOT_KEYS,
    "wall_time_s", "status", "description",
]


# ----------------------------------------------------------------
# Experiment numbering
# ----------------------------------------------------------------
def next_experiment_number() -> int:
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    nums = sorted(int(p.name) for p in EXPERIMENTS_DIR.iterdir()
                  if p.is_dir() and p.name.isdigit())
    return (nums[-1] + 1) if nums else 1


def experiment_dir(n: int) -> Path:
    return EXPERIMENTS_DIR / f"{n:04d}"


# ----------------------------------------------------------------
# Archiving
# ----------------------------------------------------------------
def archive_run(experiment_n: int,
                results: dict,
                status: str = "ok",
                topology: str = "T-rail",
                description: str = "",
                wall_time_s: float = 0.0,
                extra_files: dict | None = None,
                design_snapshot_text: str | None = None,
                preview_path: str | None = None,
                summary_path: str | None = None) -> Path:
    exp_dir = experiment_dir(experiment_n)
    exp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Frozen design.py — either explicitly provided text (parallel batch
    #    safe) or read live from disk.
    if design_snapshot_text is not None:
        (exp_dir / "design.py").write_text(design_snapshot_text)
    elif Path("design.py").exists():
        shutil.copy2("design.py", exp_dir / "design.py")

    # 2. Frozen images — explicit paths take priority (parallel-safe).
    if preview_path and Path(preview_path).exists():
        shutil.copy2(preview_path, exp_dir / "preview.png")
    elif (OUTPUT_DIR / "preview.png").exists():
        shutil.copy2(OUTPUT_DIR / "preview.png", exp_dir / "preview.png")
    if summary_path and Path(summary_path).exists():
        shutil.copy2(summary_path, exp_dir / "segmented_summary.png")
    elif (OUTPUT_DIR / "segmented_summary.png").exists():
        shutil.copy2(OUTPUT_DIR / "segmented_summary.png",
                     exp_dir / "segmented_summary.png")

    # 3. Extras
    for name, src_path in (extra_files or {}).items():
        src = Path(src_path)
        if src.exists():
            shutil.copy2(src, exp_dir / name)

    # 4. Raw frequency-domain traces — frozen for offline re-analysis.
    _save_rf_traces_npz(exp_dir, results)

    # 5. Full results.json
    payload = {
        "experiment": experiment_n,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "topology": topology,
        "description": description,
        "status": status,
        "wall_time_s": wall_time_s,
        "results": _jsonable(results),
        "knobs": _read_design_knobs(exp_dir / "design.py"),
    }
    (exp_dir / "results.json").write_text(
        json.dumps(payload, indent=2, default=str))

    # 6. TSV row
    _append_tsv_row(experiment_n, results, payload)

    # 7. Journal stub
    _append_journal_stub(experiment_n, results, payload)

    return exp_dir


def _save_rf_traces_npz(exp_dir: Path, results: dict) -> None:
    """Compress every frequency-domain array used by the FOM into a single
    npz so this experiment can be re-extracted (FOM, fits, plots) without
    re-running the cloud simulation.

    Reads the conventional `_<name>` keys from `results` and skips any that
    are missing. Writes `exp_dir / 'rf_traces.npz'`.
    """
    try:
        import numpy as np
    except Exception:
        return
    payload = {}
    for key, name in [
        ("_freqs_Hz",  "freqs_Hz"),
        ("_S11",       "S11"),
        ("_S21",       "S21"),
        ("_alpha_dBcm","alpha_dBcm"),
        ("_n_eff",     "n_eff"),
        ("_Z0",        "Z0"),
        ("_gamma",     "gamma"),
        ("_R_per_mm",  "R_per_mm"),
        ("_L_per_mm",  "L_per_mm"),
        ("_G_per_mm",  "G_per_mm"),
        ("_C_per_mm",  "C_per_mm"),
    ]:
        v = results.get(key)
        if v is None:
            continue
        payload[name] = np.asarray(v)
    if payload:
        np.savez_compressed(exp_dir / "rf_traces.npz", **payload)


def promote_best(experiment_n: int, results: dict) -> bool:
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
        src = experiment_dir(experiment_n) / "design.py"
        if src.exists():
            shutil.copy2(src, BEST_DESIGN_PY)
        return True
    return False


def revert_to_best() -> bool:
    if BEST_DESIGN_PY.exists():
        shutil.copy2(BEST_DESIGN_PY, "design.py")
        return True
    return False


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------
def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()
                if not (isinstance(k, str) and k.startswith("_"))}
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
    knobs = payload["knobs"]
    # If the snapshot specifies a TOPOLOGY string, that wins over the
    # heuristic topology label passed to archive_run.
    topology_label = knobs.get("TOPOLOGY") or payload["topology"]
    row = {
        "experiment":  n,
        "timestamp":   payload["timestamp"],
        "topology":    topology_label,
        "FOM":         _fmt(results.get("FOM")),
        "alpha_0_dBcm_per_sqrtGHz": _fmt(results.get("alpha_0_dBcm_per_sqrtGHz")),
        "alpha_at_Fref_dBcm": _fmt(results.get("alpha_at_Fref_dBcm")),
        "Z0_real_at_Fref":    _fmt(results.get("Z0_real_at_Fref")),
        "n_eff_at_Fref":      _fmt(results.get("n_eff_at_Fref")),
        "R_Ohm_per_mm_at_Fref": _fmt(results.get("R_Ohm_per_mm_at_Fref")),
        "L_nH_per_mm_at_Fref":  _fmt(results.get("L_nH_per_mm_at_Fref")),
        "G_S_per_mm_at_Fref":   _fmt(results.get("G_S_per_mm_at_Fref")),
        "C_pF_per_mm_at_Fref":  _fmt(results.get("C_pF_per_mm_at_Fref")),
        "wall_time_s": f"{payload['wall_time_s']:.1f}",
        "status":      payload["status"],
        "description": payload["description"].replace("\t", " ").replace("\n", " "),
    }
    for k in SNAPSHOT_KEYS:
        row[k] = _fmt(knobs.get(k, ""))
    with RESULTS_TSV.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t")
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def _append_journal_stub(n: int, results: dict, payload: dict) -> None:
    JOURNAL_MD.parent.mkdir(parents=True, exist_ok=True)
    exists = JOURNAL_MD.exists()
    knobs = payload["knobs"]
    knob_str = ", ".join(f"{k}={knobs.get(k)}" for k in SNAPSHOT_KEYS
                         if k in knobs)
    with JOURNAL_MD.open("a") as f:
        if not exists:
            f.write("# RF AutoDesign — Experiment Journal\n\n")
        f.write(f"## Experiment {n} — {payload['topology']}\n\n")
        f.write(f"- **Timestamp**: {payload['timestamp']}\n")
        f.write(f"- **Knobs**: {knob_str}\n")
        f.write(f"- **Hypothesis**: _(fill me in)_\n")
        f.write(f"- **Result**: FOM = {results.get('FOM')}, "
                f"α₀ = {results.get('alpha_0_dBcm_per_sqrtGHz')} dB/cm/√GHz, "
                f"Z₀(Fref) = {results.get('Z0_real_at_Fref')} Ω, "
                f"n_eff(Fref) = {results.get('n_eff_at_Fref')}\n")
        f.write(f"- **Status**: {payload['status']}\n")
        f.write(f"- **Kept or discarded**: _(fill me in)_\n")
        f.write(f"- **Lesson**: _(fill me in)_\n\n")


def _fmt(x) -> str:
    if x is None or x == "":
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
                if (exclude_experiment is not None
                        and int(row["experiment"]) == exclude_experiment):
                    continue
                fom = float(row["FOM"])
            except Exception:
                continue
            if best is None or fom > best:
                best = fom
    return best


def _read_design_knobs(design_py: Path) -> dict:
    """Cheap regex read of the agent-tunable scalars + TOPOLOGY string."""
    if not design_py.exists():
        return {}
    out = {}
    num_re = re.compile(r"^\s*([A-Z_]+[A-Z0-9_]*)\s*=\s*([0-9.eE+-]+)\s*(?:#.*)?$")
    str_re = re.compile(r"^\s*([A-Z_]+[A-Z0-9_]*)\s*=\s*[\"']([^\"'\n]*)[\"']\s*(?:#.*)?$")
    keep = set(SNAPSHOT_KEYS) | {"TOPOLOGY"}
    for line in design_py.read_text().splitlines():
        m = num_re.match(line)
        if m and m.group(1) in keep:
            try:
                out[m.group(1)] = float(m.group(2))
            except ValueError:
                out[m.group(1)] = m.group(2)
            continue
        m = str_re.match(line)
        if m and m.group(1) in keep:
            out[m.group(1)] = m.group(2)
    return out


def load_all_results() -> list[dict]:
    if not RESULTS_TSV.exists():
        return []
    with RESULTS_TSV.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))
