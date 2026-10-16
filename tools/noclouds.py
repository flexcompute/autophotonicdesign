"""Import first: any Tidy3D cloud submission raises instead of running, and mode solves run locally.

verify.py and measure.py import this, so a check never spends FlexCredits by accident (for
example a port mode solve, or a component without a cached result that falls back to FDTD).
Design work that needs FDTD runs in its own script, without this import.
"""

import photonforge as _pf
import tidy3d.web.api.container as _container
import tidy3d.web.api.webapi as _webapi


def _blocked(*args, **kwargs):
    raise RuntimeError("CLOUD BLOCKED: a check tried to submit a Tidy3D cloud task. "
                       "Characterize the component first (own script), so the check uses cached or analytic data.")


for _name in ("upload", "start", "run", "run_async"):
    if hasattr(_webapi, _name):
        setattr(_webapi, _name, _blocked)
# PhotonForge submits through tidy3d.web.Job, which keeps its own references to the functions above.
for _name in ("upload", "start", "run"):
    if hasattr(_container.Job, _name):
        setattr(_container.Job, _name, _blocked)

# Port mode solves (needed by the circuit simulation) run on this machine (needs tidy3d-extras).
_pf.config.use_local_mode_solver = True
