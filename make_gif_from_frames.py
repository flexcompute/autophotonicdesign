"""make_gif_from_frames.py  ──  stitch the captured LiveViewer screenshots into a captioned GIF.

Frames are the ACTUAL LiveViewer screenshots in output/frames/NNNN.png (captured by optimize.py).
Each frame's caption leads with the TITLE stating WHAT CHANGED that step (the `change` string the
loop recorded in result.json — e.g. "fill x5 (160 devices)" or "squeeze: method blsf->bssf"), then
the FOM / structures / fill line and the fixed-die / verdict line.
"""
import sys, glob, json, pathlib, warnings

warnings.filterwarnings("ignore", message=".*renamed in the layout.*")
ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))
from tools import toolbox as T


frames, captions = [], []
for fp in sorted(glob.glob(str(ROOT / "output" / "frames" / "*.png"))):
    n = int(pathlib.Path(fp).stem)
    res = ROOT / "output" / "experiments" / f"{n:04d}" / "result.json"
    if not res.exists():
        continue
    try:
        r = json.loads(res.read_text())
    except Exception:  # noqa: BLE001
        continue
    frames.append(fp)
    captions.append([
        f"exp {r['exp']:02d}   {r.get('change', 'refine')}",
        f"FOM {r['fom']:.0f}   |   {r['n_placed']} devices   |   {r['fill_fraction']*100:.0f}% full",
        f"{r['die_w_um']/1000:.0f} x {r['die_h_um']/1000:.0f} mm fixed   |   "
        f"{'PASS' if r['passes'] else 'FAIL'}   |   prober-aligned",
    ])

if not frames:
    print("no frames yet")
    raise SystemExit
out = str(ROOT / "output" / "evolution.gif")
fps = float(sys.argv[1]) if len(sys.argv) > 1 else 1.8
g = T.make_gif(frames, out, fps=fps, captions=captions)
print(f"wrote {g} from {len(frames)} LiveViewer frames (fps={fps})" if g else "GIF build failed")
