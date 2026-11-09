"""Score the reviewers' board against the answer key.

    python tools/red/score.py ../runs/siepic_s7/red ../runs/siepic_s7/sandbox     -> red/score.json and a table

A finding matches the one plant nearest to its bbox, within MARGIN um (between plants that it touches, the one that it
overlaps most). A plant is found when one finding matches it. Chip-wide findings (bbox over a quarter of the chip) match nothing. For mistakes and easy ones, the highest
severity of the matching findings is compared with the key. For harmless changes, a matching finding rated medium or
high is a false alarm; one rated none or low is a correct dismissal. Findings that match no plant are listed for a
person to judge (a real issue in the clean design, or a false alarm), with an optional adjudication.json in red/:
{"<finding id>": "reason"} removes a finding from the matching.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

MARGIN = 10.0
RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def box(d):
    b = d.get("bbox")
    try:
        if isinstance(b, (list, tuple)) and len(b) == 4:
            return [float(v) for v in b]
        if d.get("x") is not None and d.get("y") is not None:
            x, y = float(d["x"]), float(d["y"])
            return [x, y, x, y]
    except (TypeError, ValueError):
        pass
    return None


def gap(fb, pb):
    """Distance between two boxes (0 when they overlap)."""
    dx = max(pb[0] - fb[2], fb[0] - pb[2], 0.0)
    dy = max(pb[1] - fb[3], fb[1] - pb[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


def overlap(fb, pb):
    w = min(fb[2], pb[2]) - max(fb[0], pb[0])
    h = min(fb[3], pb[3]) - max(fb[1], pb[1])
    return max(w, 0.0) * max(h, 0.0)


def nearest(fb, plants, m):
    """The one plant a finding points to: the nearest within m um; between plants it touches, the one it overlaps most."""
    c = [(gap(fb, p["bbox"]), -overlap(fb, p["bbox"]), p["id"]) for p in plants]
    c = [x for x in c if x[0] <= m]
    return [min(c)[2]] if c else []


def main(red, sandbox):
    red, sandbox = Path(red), Path(sandbox)
    key = json.loads((red / "answer_key.json").read_text())
    plants = key["plants"]
    adj = json.loads((red / "adjudication.json").read_text()) if (red / "adjudication.json").exists() else {}
    findings = []
    for f in sorted((sandbox / "board").glob("*.jsonl")):
        for line in open(f):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            d["_file"] = f.stem
            findings.append(d)
    chip = json.loads((sandbox / "chip" / "chip.json").read_text())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import review as rv
    rv.configure(sandbox / "chip" / chip["gds"], chip["top"], chip["pdk"], cache=red / "cache_score")
    x0, y0, x1, y1 = rv.summary()["bbox"]
    chip_area = (x1 - x0) * (y1 - y0)
    primary = [d for d in findings if not d.get("confirms") and not d.get("disputes")]
    reviews = [d for d in findings if d.get("confirms") or d.get("disputes")]
    match, unmatched, chipwide = defaultdict(list), [], []
    for d in primary:
        fb = box(d)
        if d.get("id") in adj or (fb and (fb[2] - fb[0]) * (fb[3] - fb[1]) > 0.25 * chip_area):
            chipwide.append(d)
            d["_plants"] = []
            continue
        got = nearest(fb, plants, MARGIN) if fb else []
        d["_plants"] = got
        for g in got:
            match[g].append(d)
        if not got:
            unmatched.append(d)
    by_id = {d.get("id"): d for d in primary}
    confirmed = defaultdict(set)
    for r in reviews:
        ref = r.get("confirms") or r.get("disputes")
        for x in (ref if isinstance(ref, list) else [ref]):
            for g in by_id.get(x, {}).get("_plants", []):
                confirmed[g].add(r.get("reviewer", r["_file"]))
    rows = []
    for p in plants:
        ms = match.get(p["id"], [])
        sev = max((RANK.get(str(d.get("severity", "")).lower(), -1) for d in ms), default=-1)
        rows.append(dict(id=p["id"], kind=p["kind"], key_severity=p["severity"], found=bool(ms),
                         best_severity=next((s for s, v in RANK.items() if v == sev), None),
                         reviewers=sorted({d.get("reviewer", d["_file"]) for d in ms}),
                         first_time=min((d.get("time", "9999") for d in ms), default=None),
                         first_by=min(ms, key=lambda d: d.get("time", "9999")).get("reviewer") if ms else None,
                         confirmed_by=sorted(confirmed.get(p["id"], set())), n_findings=len(ms), title=p["title"],
                         drc=p.get("drc", []), lvs=bool(p.get("lvs"))))
    mist = [r for r in rows if r["kind"] == "mistake"]
    easy = [r for r in rows if r["kind"] == "easy"]
    harm = [r for r in rows if r["kind"] == "harmless"]
    alarms = [r for r in harm if r["found"] and RANK.get(r["best_severity"] or "none", 0) >= 2]
    sev_ok = [r for r in mist + easy if r["found"] and r["best_severity"] == r["key_severity"]]
    out = dict(case=key["case"], pdk=key["pdk"], seed=key["seed"], n_findings=len(primary), n_reviews=len(reviews),
               mistakes_found=sum(r["found"] for r in mist), mistakes=len(mist),
               easy_found=sum(r["found"] for r in easy), easy=len(easy),
               harmless_reported=sum(r["found"] for r in harm), harmless_raised_as_defects=len(alarms), harmless=len(harm),
               severity_exact=len(sev_ok), severity_scored=sum(r["found"] for r in mist + easy), unmatched=len(unmatched),
               plants=rows, chipwide=[dict(id=d.get("id"), title=d.get("title")) for d in chipwide],
               unmatched_findings=[dict(id=d.get("id"), reviewer=d.get("reviewer"), title=d.get("title"),
                                        severity=d.get("severity"), bbox=box(d)) for d in unmatched])
    (red / "score.json").write_text(json.dumps(out, indent=1))
    print(f"{key['case']}: findings {len(primary)} (+{len(reviews)} reviews); mistakes {out['mistakes_found']}/{len(mist)}, "
          f"easy {out['easy_found']}/{len(easy)}, harmless reported {out['harmless_reported']}/{len(harm)} "
          f"(as defects {len(alarms)}), severity as key {len(sev_ok)}/{out['severity_scored']}, unmatched {len(unmatched)}")
    for r in rows:
        print(f"  {r['id']} {r['kind']:8s} key={r['key_severity']:6s} found={'Y' if r['found'] else '-'} "
              f"best={r['best_severity']} first={r['first_by']} by={r['reviewers']} {r['title'][:70]}")
    return out


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
