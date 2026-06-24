"""Structured events and file logging under recordings/logs/."""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any

from meetrec.config import load_config

_events = logging.getLogger("meetrec.events")
_configured_role: str | None = None


def log_dir(recordings_dir: str | None = None) -> str:
    if recordings_dir is None:
        recordings_dir = load_config().get("recordings_dir", "")
    path = os.path.join(recordings_dir, "logs")
    os.makedirs(path, exist_ok=True)
    return path


def log_file_path(role: str, recordings_dir: str | None = None) -> str:
    day = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(log_dir(recordings_dir), f"meetrec-{role}-{day}.log")


def setup_process_logging(role: str) -> str:
    """Console (if any) + daily log file next to recordings. Returns log file path."""
    global _configured_role
    cfg = load_config()
    path = log_file_path(role, cfg.get("recordings_dir"))
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Frozen GUI has no console; dev / subprocess may still use stderr.
    if not getattr(sys, "frozen", False) or role != "gui":
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)

    _configured_role = role
    logging.getLogger(__name__).info("process_start role=%s log_file=%s", role, path)
    return path


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, "timestamp": datetime.now().isoformat(timespec="seconds"), **fields}
    _events.info(json.dumps(payload, ensure_ascii=False))
