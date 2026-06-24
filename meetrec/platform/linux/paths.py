"""Linux CI stub paths (tests only — app does not run on Linux)."""

from __future__ import annotations

import os

APP_NAME = "Desktop Meeting Recorder"
APP_ID = "meetrec"
LEGACY_APP_NAME = "Ghost Meet Recorder"

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LEGACY_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", LEGACY_APP_NAME)
LEGACY_SETTINGS = os.path.join(LEGACY_CONFIG_DIR, "settings.json")
LOCK_FILE = os.path.join(CONFIG_DIR, "meetrec.lock")

DEFAULT_RECORDINGS_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "Desktop Meeting Recordings"
)

BROWSER_PROCESSES: set[str] = set()
