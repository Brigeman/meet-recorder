"""macOS autostart via LaunchAgent plist."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys

from meetrec.platform.macos.paths import AUTOSTART_KEY, AUTOSTART_LABEL

PLIST_PATH = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", f"{AUTOSTART_KEY}.plist")


def is_supported() -> bool:
    return sys.platform == "darwin"


def current_executable_path() -> str | None:
    if not getattr(sys, "frozen", False):
        return None
    exe = os.path.abspath(sys.executable)
    if not exe.endswith("MeetRec"):
        return None
    return exe


def get_registered_path() -> str | None:
    if not os.path.isfile(PLIST_PATH):
        return None
    try:
        with open(PLIST_PATH, "rb") as f:
            data = plistlib.load(f)
        args = data.get("ProgramArguments") or []
        return str(args[0]) if args else None
    except (OSError, plistlib.InvalidFileException, TypeError, ValueError):
        return None


def is_enabled() -> bool:
    return bool(get_registered_path())


def enable(executable: str | None = None) -> bool:
    exe = executable or current_executable_path()
    if not exe:
        return False
    exe = os.path.abspath(exe)
    os.makedirs(os.path.dirname(PLIST_PATH), exist_ok=True)
    payload = {
        "Label": AUTOSTART_LABEL,
        "ProgramArguments": [exe],
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
    }
    try:
        with open(PLIST_PATH, "wb") as f:
            plistlib.dump(payload, f)
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", PLIST_PATH],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", PLIST_PATH],
            capture_output=True,
            check=True,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def disable() -> bool:
    if not os.path.isfile(PLIST_PATH):
        return True
    try:
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", PLIST_PATH],
            capture_output=True,
            check=False,
        )
        os.remove(PLIST_PATH)
        return True
    except OSError:
        return False
