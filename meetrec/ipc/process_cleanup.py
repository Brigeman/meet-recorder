"""Reap orphaned meetrec worker processes before GUI startup."""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def _worker_role(cmdline: list[str]) -> str | None:
    if not cmdline:
        return None
    joined = " ".join(cmdline).lower()
    if "detector" in joined and "meetrec" in joined:
        return "detector"
    if "recorder" in joined and "meetrec" in joined:
        return "recorder"
    if len(cmdline) >= 2:
        exe = os.path.basename(cmdline[0]).lower()
        arg = cmdline[1].lower()
        if "meetrec" in exe and arg in ("detector", "recorder"):
            return arg
    return None


def reap_stale_workers() -> None:
    """Terminate detector/recorder processes not owned by this GUI session."""
    try:
        import psutil
    except Exception:
        return

    my_pid = os.getpid()
    for proc in psutil.process_iter(["pid", "ppid", "cmdline"]):
        try:
            pid = proc.info.get("pid")
            if not pid or pid == my_pid:
                continue
            role = _worker_role(proc.info.get("cmdline") or [])
            if not role:
                continue
            ppid = proc.info.get("ppid")
            if ppid == my_pid:
                continue
            if ppid == 1:
                log.warning("reaping orphan %s pid=%s (ppid=launchd)", role, pid)
                proc.terminate()
                continue
            try:
                psutil.Process(ppid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                log.warning("reaping stale %s pid=%s (parent pid=%s gone)", role, pid, ppid)
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
