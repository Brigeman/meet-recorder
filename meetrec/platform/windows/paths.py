"""Windows configuration paths."""

from __future__ import annotations

import os

APP_NAME = "Desktop Meeting Recorder"
APP_ID = "meetrec"
LEGACY_APP_NAME = "Ghost Meet Recorder"
AUTOSTART_KEY = "MeetRec"

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", ""), APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LEGACY_CONFIG_DIR = os.path.join(os.environ.get("APPDATA", ""), LEGACY_APP_NAME)
LEGACY_SETTINGS = os.path.join(LEGACY_CONFIG_DIR, "settings.json")
LOCK_FILE = os.path.join(CONFIG_DIR, "meetrec.lock")

DEFAULT_RECORDINGS_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "Desktop Meeting Recordings"
)

BROWSER_PROCESSES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"}
