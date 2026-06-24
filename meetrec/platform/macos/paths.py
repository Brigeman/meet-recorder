"""macOS configuration paths."""

from __future__ import annotations

import os

APP_NAME = "Desktop Meeting Recorder"
APP_ID = "meetrec"
LEGACY_APP_NAME = "Ghost Meet Recorder"
AUTOSTART_KEY = "ai.o2consult.meetrec"
AUTOSTART_LABEL = "ai.o2consult.meetrec"

CONFIG_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LEGACY_CONFIG_DIR = os.path.join(
    os.path.expanduser("~"), "Library", "Application Support", LEGACY_APP_NAME
)
LEGACY_SETTINGS = os.path.join(LEGACY_CONFIG_DIR, "settings.json")
LOCK_FILE = os.path.join(CONFIG_DIR, "meetrec.lock")

DEFAULT_RECORDINGS_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "Desktop Meeting Recordings"
)

BROWSER_PROCESSES = {
    "Google Chrome",
    "Google Chrome Helper",
    "Microsoft Edge",
    "Microsoft Edge Helper",
    "firefox",
    "Brave Browser",
    "Opera",
    "Safari",
    "SafariForWebKitDevelopment",
}
