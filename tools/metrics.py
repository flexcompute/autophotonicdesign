"""Metrics library. spec.yaml picks a metric by `type` and gives its arguments and targets.

Every metric takes the wavelength grid (um) and the measured or simulated power transmission
(linear) and returns a dict of named values. Add a new metric as a function plus an entry in
METRICS; the rest of the harness does not change.
"""

import numpy as np


def db(x):
    return 10 * np.log10(np.maximum(np.asarray(x, float), 1e-15))


def channel(wl, t, *, center, pass_halfwidth, stop_offsets=(), stop_halfwidth=0.0):
    """A pass band at `center` +- pass_halfwidth and stop bands at center + offset +- stop_halfwidth.

    insertion_loss_db: worst (largest) loss in the pass band, positive dB
    ripple_db:         max - min in the pass band
    isolation_db:      worst pass-band level minus worst (highest) stop-band level
    bw_1db_nm:         width of the region around the pass-band peak within 1 dB of the peak
    center_error_nm:   middle of that 1-dB region minus `center`
    """
    wl, d = np.asarray(wl, float), db(t)
    pas = np.abs(wl - center) <= pass_halfwidth
    if not pas.any():
        raise ValueError("pass band has no wavelength points")
    out = {"insertion_loss_db": float(-d[pas].min()), "ripple_db": float(d[pas].max() - d[pas].min())}
    stop = np.zeros_like(pas)
    for o in stop_offsets:
        stop |= np.abs(wl - (center + o)) <= stop_halfwidth
    if stop.any():
        out["isolation_db"] = float(d[pas].min() - d[stop].max())
    i = np.flatnonzero(pas)[np.argmax(d[pas])]
    lo = hi = i
    while lo > 0 and d[lo - 1] >= d[i] - 1:
        lo -= 1
    while hi < d.size - 1 and d[hi + 1] >= d[i] - 1:
        hi += 1
    out["bw_1db_nm"] = float((wl[hi] - wl[lo]) * 1e3)
    out["center_error_nm"] = float(((wl[hi] + wl[lo]) / 2 - center) * 1e3)
    return out


def insertion_loss(wl, t, *, band=None):
    """Worst insertion loss (positive dB) over `band` = [lo, hi] um (default: all points)."""
    wl, d = np.asarray(wl, float), db(t)
    m = np.ones_like(wl, bool) if band is None else (wl >= band[0]) & (wl <= band[1])
    return {"insertion_loss_db": float(-d[m].min())}


def imbalance(wl, t, *, other, band=None):
    """Worst |t - other| in dB over `band` (for splitters). `other` is the second path's transmission."""
    wl = np.asarray(wl, float)
    m = np.ones_like(wl, bool) if band is None else (wl >= band[0]) & (wl <= band[1])
    return {"imbalance_db": float(np.max(np.abs(db(t)[m] - db(other)[m])))}


METRICS = {"channel": channel, "insertion_loss": insertion_loss, "imbalance": imbalance}


def check(values: dict, targets: dict) -> list[dict]:
    """Compare values with targets {name: {min: x} | {max: x} | {abs_max: x}}. One row per target."""
    rows = []
    for name, rule in targets.items():
        v = values.get(name)
        ok = v is not None
        if ok and "min" in rule:
            ok = v >= rule["min"]
        if ok and "max" in rule:
            ok = v <= rule["max"]
        if ok and "abs_max" in rule:
            ok = abs(v) <= rule["abs_max"]
        rows.append({"metric": name, "value": v, "target": rule, "ok": bool(ok)})
    return rows
