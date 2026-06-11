"""
Viewer navigation for the AI.

Two ways the agent moves around the layout to inspect violations:

1. Re-render a chosen node (the reliable "zoom to / choose hierarchy" + "show violations"):
   `to_view(chip, focus="heater_length100", show_violations=True)` returns the component to push
   to the LiveViewer — either the whole chip, or just one sub-component, optionally with the
   exact-collision overlay painted on. `view_doe.py` honours the env vars PF_FOCUS / PF_SHOW so
   the agent can restart the viewer focused on any node.

2. Drive the LiveViewer GUI directly with the `mcp__Claude_Preview__preview_eval` browser tool:
   inject `NAV_JS` once, then call `pfnav.resetView()`, `pfnav.zoomIn()`, `pfnav.moreLevels()`
   (deeper hierarchy), `pfnav.fewerLevels()`, `pfnav.layers()` (Display options / layer toggles),
   and `preview_screenshot` to capture. `pfnav.buttons()` lists what is available.
"""
import os

import photonforge as pf

from . import hierarchy, validation


def to_view(chip, *, focus=None, show_violations=False, layer=validation.WG,
            collisions=None, drc_lyrdb=None):
    """Component to display: optionally a single hierarchy node, optionally with a collision overlay."""
    node = chip
    if focus:
        hit = hierarchy.find(chip, focus)
        if hit is not None:
            node = hit
    if show_violations:
        overlay, _ = validation.collision_map(node, layer)
        # also paint M2/M1 + bondpad + DRC markers if a full report was supplied
        if collisions is not None:
            from . import violations as _vio
            overlay2, _ = _vio.annotate(node, collisions, drc_lyrdb=drc_lyrdb)
            return overlay2
        return overlay
    return node


def view_target_from_env(chip, **kw):
    """Read PF_FOCUS / PF_SHOW so a restarted viewer lands on the right node/overlay."""
    focus = os.environ.get("PF_FOCUS") or None
    show = os.environ.get("PF_SHOW", "").lower() in ("violations", "collisions", "1", "true")
    return to_view(chip, focus=focus, show_violations=show, **kw)


# Injected once via preview_eval; then call pfnav.<action>() in later preview_eval calls.
NAV_JS = r"""
window.pfnav = (function () {
  const btn = (t) => Array.from(document.querySelectorAll('button'))
      .find(b => ((b.title || b.getAttribute('aria-label') || '').toLowerCase()).includes(t));
  const click = (t) => { const b = btn(t); if (b) { b.click(); return true; } return false; };
  const cvs = () => document.querySelector('canvas') || document.querySelector('svg');
  const wheel = (dy, n) => { const c = cvs(); const r = c.getBoundingClientRect();
    for (let i = 0; i < (n || 1); i++) c.dispatchEvent(new WheelEvent('wheel',
      { clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, deltaY: dy, bubbles: true })); };
  return {
    resetView: () => click('reset view'),
    fit: () => click('reset view'),
    moreLevels: (n) => { for (let i = 0; i < (n || 1); i++) click('more levels'); },
    fewerLevels: (n) => { for (let i = 0; i < (n || 1); i++) click('fewer levels'); },
    layers: () => click('display options'),
    grid: () => click('toggle grid'),
    theme: () => click('toggle theme'),
    zoomIn: (n) => wheel(-150, n || 4),
    zoomOut: (n) => wheel(150, n || 4),
    buttons: () => Array.from(document.querySelectorAll('button'))
        .map(b => b.title || b.getAttribute('aria-label')).filter(Boolean),
  };
})();
'pfnav ready: ' + window.pfnav.buttons().join(', ')
"""
