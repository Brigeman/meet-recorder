"""COM apartment init for WASAPI probes (detector)."""

from __future__ import annotations

import comtypes

# RPC_E_CHANGED_MODE — thread already has a different apartment model.
_RPC_E_CHANGED_MODE = -2147417850


def ensure_com() -> None:
    """Initialize COM once; ignore if already initialized (e.g. by pycaw import)."""
    try:
        comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    except OSError as e:
        if getattr(e, "winerror", None) != _RPC_E_CHANGED_MODE:
            raise
