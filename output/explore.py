"""Explore Euler-bend geometry: compute clothoid-arc-clothoid centerline with
fixed endpoints (0, 0) and (12, 12), total angle 90 deg.
"""
import numpy as np


def euler_path(p: float, N: int = 4001, endpoint=(12.0, 12.0)):
    """Clothoid-arc-clothoid centerline.

    p: fraction of the total 90-deg swept by the two clothoids (p in [0, 1]).
       p = 0  -> pure circular arc
       p = 1  -> pure Euler (no circular middle).

    Returns (x, y, theta, R_min, scale) where R_min is the min radius of
    curvature (at the midpoint), and scale is the length scale factor.
    """
    if p <= 1e-6:
        theta = np.linspace(0.0, np.pi / 2, N)
        xc = np.sin(theta)
        yc = 1.0 - np.cos(theta)
        scale = endpoint[0] / xc[-1]
        return xc * scale, yc * scale, theta, scale, scale

    # parameterize in a unit frame with clothoid length s1 = 1, scale at end.
    s1 = 1.0
    theta1 = p * np.pi / 4
    theta2 = np.pi / 2 - theta1
    Kmax = 2.0 * theta1 / s1                  # K at s = s1
    arc_len = (theta2 - theta1) / Kmax        # middle circular arc length
    s_mid_end = s1 + arc_len
    L = 2.0 * s1 + arc_len

    s = np.linspace(0.0, L, N)
    theta = np.empty_like(s)

    m1 = s <= s1
    theta[m1] = theta1 * (s[m1] / s1) ** 2
    m2 = (s > s1) & (s <= s_mid_end)
    theta[m2] = theta1 + Kmax * (s[m2] - s1)
    m3 = s > s_mid_end
    sm = L - s[m3]                            # mirror coordinate (0 .. s1)
    theta[m3] = np.pi / 2 - theta1 * (sm / s1) ** 2

    cs = np.cos(theta)
    ss = np.sin(theta)
    dx = 0.5 * (cs[:-1] + cs[1:]) * np.diff(s)
    dy = 0.5 * (ss[:-1] + ss[1:]) * np.diff(s)
    xc = np.concatenate(([0.0], np.cumsum(dx)))
    yc = np.concatenate(([0.0], np.cumsum(dy)))

    scale = endpoint[0] / xc[-1]
    R_min = scale / Kmax                      # real-world R_min after scaling
    return xc * scale, yc * scale, theta, R_min, scale


if __name__ == "__main__":
    print(f"{'p':>5}  {'L':>7}  {'R_min':>7}  {'xc_end':>8}  {'yc_end':>8}")
    for p in [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        x, y, th, R_min, scale = euler_path(p)
        L_num = np.sum(np.sqrt(np.diff(x) ** 2 + np.diff(y) ** 2))
        print(f"{p:5.2f}  {L_num:7.3f}  {R_min:7.3f}  {x[-1]:8.4f}  {y[-1]:8.4f}")
