"""Shared files: journal, status of the phases, cloud cost.

    python tools/team.py init                                     # one time, before the first phase
    python tools/team.py log --role architect --event decision --msg "dL 40/80 um: FSR 10 nm"
    python tools/team.py log --role component --event cloud --msg "DC gap sweep, 6 FDTD" --cost 0.42
    python tools/team.py status                                   # targets, achieved values, reviews, gates, journal

Events: plan, decision, result, gate, review, fix, blocked, cloud, lesson, note.
"""

import argparse
import glob
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM = os.path.join(ROOT, "team")
JOURNAL = os.path.join(TEAM, "journal.jsonl")
EVENTS = ["plan", "decision", "result", "gate", "review", "fix", "blocked", "cloud", "lesson", "note"]


def init():
    for d in ("targets", "achieved", "reviews"):
        os.makedirs(os.path.join(TEAM, d), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    if not os.path.exists(JOURNAL):
        open(JOURNAL, "w").close()
    print("team/ ready:", ", ".join(sorted(os.listdir(TEAM))))


def log(role, event, msg, files=None, cost=None):
    if event not in EVENTS:
        raise SystemExit(f"event must be one of {EVENTS}")
    row = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "role": role, "event": event, "msg": msg}
    if files:
        row["files"] = files
    if cost is not None:
        row["cost_fc"] = float(cost)
    with open(JOURNAL, "a") as f:
        f.write(json.dumps(row) + "\n")
    print(f"logged: [{role}] {event}: {msg}")


def _rows():
    if not os.path.exists(JOURNAL):
        return []
    with open(JOURNAL) as f:
        return [json.loads(line) for line in f if line.strip()]


def status(n=12):
    rows = _rows()
    print("== targets (architect) ==")
    for p in sorted(glob.glob(os.path.join(TEAM, "targets", "*.json"))):
        print("  ", os.path.basename(p))
    print("== achieved (component) ==")
    for p in sorted(glob.glob(os.path.join(TEAM, "achieved", "*.json"))):
        try:
            with open(p) as f:
                d = json.load(f)
            print(f"   {os.path.basename(p)}: meets_target={d.get('meets_target')} binding={d.get('binding_constraint', '-')}")
        except Exception as e:
            print(f"   {os.path.basename(p)}: unreadable ({e})")
    print("== reviews (judge) ==")
    for p in sorted(glob.glob(os.path.join(TEAM, "reviews", "*.md"))):
        with open(p) as f:
            first = next((line.strip() for line in f if line.strip()), "")
        print(f"   {os.path.basename(p)}: {first[:80]}")
    v = os.path.join(ROOT, "output", "verify.json")
    print("== last verify ==")
    if os.path.exists(v):
        with open(v) as f:
            r = json.load(f)
        print("  ", r["time"], " ".join(f"{g}:{'PASS' if x['ok'] else 'FAIL'}" for g, x in r["gates"].items()))
    else:
        print("   none yet")
    spend = sum(r.get("cost_fc", 0.0) for r in rows)
    print(f"== cloud spend: {spend:.2f} FlexCredits in {sum(1 for r in rows if r['event'] == 'cloud')} logged runs ==")
    print(f"== journal (last {n} of {len(rows)}) ==")
    for r in rows[-n:]:
        print(f"   {r['time'][5:16]} [{r['role']}] {r['event']}: {r['msg'][:110]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    lg = sub.add_parser("log")
    lg.add_argument("--role", required=True)
    lg.add_argument("--event", required=True)
    lg.add_argument("--msg", required=True)
    lg.add_argument("--files", nargs="*")
    lg.add_argument("--cost", type=float, default=None, help="FlexCredits spent (cloud events)")
    st = sub.add_parser("status")
    st.add_argument("-n", type=int, default=12)
    a = ap.parse_args()
    if a.cmd == "init":
        init()
    elif a.cmd == "log":
        log(a.role, a.event, a.msg, a.files, a.cost)
    else:
        status(a.n)


if __name__ == "__main__":
    main()
