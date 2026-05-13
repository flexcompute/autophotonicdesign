"""
design.py — Routing strategy for the projector-chip auto-design agent.

THE AGENT MODIFIES THIS FILE.

A 32-net PhotonForge projector circuit (16 AMZIs + bondpads) is fixed.
The agent tunes the routing strategy by editing:

    MODE        — "manhattan_indep", "manhattan_seq", or "grid"
    CONFIG      — dict of router parameters (algorithm, grid pitch,
                  obstacle inflation, bondpad layout, etc.)

For the grid maze router (`MODE = "grid"`), CONFIG["ALGORITHM"] can be:
    "BFS", "A*", "Bundle", "Rip-Up", "Hybrid"

For the Manhattan baseline (`MODE = "manhattan_*"`), only TRACE_WIDTH +
bondpad placement keys are used.

The shipped baseline is `manhattan_indep` — the naive Manhattan router
that produced 192 DRC violations in iteration 1 of the published run.
"""
from __future__ import annotations

import sys
import os

# Make tools/ importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))

from runners import cfg_defaults


# =========================================================================
# Routing mode (agent tunes this)
# =========================================================================
MODE: str = "manhattan_indep"


# =========================================================================
# Routing configuration (agent tunes this)
# =========================================================================
CONFIG: dict = cfg_defaults(
    # Default algorithm only takes effect when MODE == "grid"
    ALGORITHM="Hybrid",
    GRID_PITCH=15.0,
    TRACE_WIDTH=15.0,
    INFLATE_UM=0.0,
    MARGIN=1,
    M1_MARGIN=1,
    BLOCK_M1=False,    # Iter-1 baseline ignores M1_heater obstacles
)


# =========================================================================
# Hooks expected by route.py
# =========================================================================
def get_mode() -> str:
    return MODE


def get_config() -> dict:
    return CONFIG


def snapshot_header() -> str:
    return (
        f"# MODE={MODE}  ALGORITHM={CONFIG['ALGORITHM']}\n"
        f"# GRID_PITCH={CONFIG['GRID_PITCH']}  INFLATE_UM={CONFIG['INFLATE_UM']}\n"
        f"# TRACE_WIDTH={CONFIG['TRACE_WIDTH']}  BLOCK_M1={CONFIG['BLOCK_M1']}"
    )
