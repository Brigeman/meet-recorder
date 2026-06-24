"""Windows platform adapter."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys

from meetrec.platform.windows import (
    apps,
    audio,
    autostart,
    browser,
    capture,
    com_init,
    foreground,
    paths,
)

APP_ID = paths.APP_ID
BROWSER_PROCESSES = paths.BROWSER_PROCESSES
CONFIG_DIR = paths.CONFIG_DIR
CONFIG_FILE = paths.CONFIG_FILE
LEGACY_CONFIG_DIR = paths.LEGACY_CONFIG_DIR
LEGACY_SETTINGS = paths.LEGACY_SETTINGS
LOCK_FILE = paths.LOCK_FILE
DEFAULT_RECORDINGS_DIR = paths.DEFAULT_RECORDINGS_DIR

AudioCapture = capture.AudioCapture

probe_foreground = foreground.probe_foreground
probe_audio_activity = audio.probe_audio_activity
probe_meeting_app_audio = audio.probe_meeting_app_audio
probe_browser_meeting = browser.probe_browser_meeting
mic_used_by_meeting_process = audio.mic_used_by_meeting_process

resolve_app_for_pid = apps.resolve_app_for_pid
list_running_meeting_apps = apps.list_running_meeting_apps
list_running_meeting_pids = apps.list_running_meeting_pids
match_title_hint = apps.match_title_hint
match_in_call_title = apps.match_in_call_title

autostart_is_supported = autostart.is_supported
autostart_current_executable_path = autostart.current_executable_path
autostart_get_registered_path = autostart.get_registered_path
autostart_is_enabled = autostart.is_enabled
autostart_enable = autostart.enable
autostart_disable = autostart.disable

ensure_native_init = com_init.ensure_com


def open_path(path: str) -> None:
    os.startfile(path)  # type: ignore[attr-defined]


def show_message(message: str, title: str, flags: int = 0) -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, flags)
    except Exception:
        pass


def set_app_user_model_id(app_id: str) -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def frozen_module_cmd(module: str) -> list[str]:
    if not getattr(sys, "frozen", False):
        if module.endswith("detector.service"):
            return [sys.executable, "-m", "meetrec", "detector"]
        if module.endswith("recorder.service"):
            return [sys.executable, "-m", "meetrec", "recorder"]
        return [sys.executable, "-m", module]
    base = os.path.dirname(sys.executable)
    if module.endswith("detector.service"):
        return [os.path.join(base, "WinRec.Detector.exe")]
    if module.endswith("recorder.service"):
        return [os.path.join(base, "WinRec.Recorder.exe")]
    return [sys.executable, "-m", module]


def app_icon_path(resources_dir: str) -> str:
    return os.path.join(resources_dir, "meetrec.ico")


def executable_name_matches(name: str | None) -> bool:
    lowered = (name or "").lower()
    return "winrec" in lowered or "meetrec" in lowered or "python" in lowered


def get_scoring_weights() -> dict[str, int]:
    return {
        "mic_active": 25,
        "loopback_active": 20,
        "meeting_app_capture_active": 30,
        "meeting_app_render_active": 20,
        "meeting_app_network_active": 25,
        "in_call_title": 25,
        "known_meeting_app_running": 10,
        "known_meeting_app_foreground": 15,
        "title_hint": 10,
        "browser_meeting_context": 40,
    }
