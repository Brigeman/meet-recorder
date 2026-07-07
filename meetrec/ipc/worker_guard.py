"""Watchdog for detector/recorder worker processes."""

from __future__ import annotations

import logging
import os
import threading
import time

log = logging.getLogger(__name__)

_POLL_SEC = 2.0


def start_parent_watchdog() -> None:
    """Exit the worker when the GUI parent process is gone (reparented to launchd)."""
    try:
        import psutil

        parent = psutil.Process(os.getppid())
    except Exception:
        return

    def _watch() -> None:
        while True:
            time.sleep(_POLL_SEC)
            try:
                if os.getppid() == 1:
                    log.info("parent gone (ppid=1); worker exiting")
                    os._exit(0)
                parent.status()
            except Exception:
                log.info("parent process gone; worker exiting")
                os._exit(0)

    threading.Thread(target=_watch, name="parent-watchdog", daemon=True).start()
