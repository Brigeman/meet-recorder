"""Windows autostart management via HKCU Run key."""

from __future__ import annotations

import os
import platform
import sys

from meetrec.platform.windows.paths import AUTOSTART_KEY

RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_supported() -> bool:
    return platform.system() == "Windows"


def current_executable_path() -> str | None:
    if not getattr(sys, "frozen", False):
        return None
    exe = os.path.abspath(sys.executable)
    lowered = exe.lower()
    if not (lowered.endswith("meetrec.exe") or lowered.endswith("meetrec.exe")):
        return None
    return exe


def get_registered_path() -> str | None:
    if not is_supported():
        return None
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, AUTOSTART_KEY)
            return str(value).strip().strip('"')
    except OSError:
        return None


def is_enabled() -> bool:
    return bool(get_registered_path())


def enable(executable: str | None = None) -> bool:
    if not is_supported():
        return False
    try:
        import winreg
    except ImportError:
        return False

    exe = executable or current_executable_path()
    if not exe:
        return False
    exe = os.path.abspath(exe)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, AUTOSTART_KEY, 0, winreg.REG_SZ, f'"{exe}"')
        return True
    except OSError:
        return False


def disable() -> bool:
    if not is_supported():
        return False
    try:
        import winreg
    except ImportError:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, AUTOSTART_KEY)
        return True
    except OSError:
        return False
