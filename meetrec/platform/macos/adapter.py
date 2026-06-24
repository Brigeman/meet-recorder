"""macOS platform adapter."""

from __future__ import annotations

import os
import subprocess
import sys

from meetrec.detector.titles import match_in_call_title, match_title_hint
from meetrec.platform.macos import apps, audio, autostart, browser, capture, foreground, paths

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

autostart_is_supported = autostart.is_supported
autostart_current_executable_path = autostart.current_executable_path
autostart_get_registered_path = autostart.get_registered_path
autostart_is_enabled = autostart.is_enabled
autostart_enable = autostart.enable
autostart_disable = autostart.disable


def ensure_native_init() -> None:
    return None


def open_path(path: str) -> None:
    subprocess.run(["open", path], check=False)


def show_message(message: str, title: str, flags: int = 0) -> None:
    _ = flags
    try:
        escaped = message.replace('"', '\\"')
        escaped_title = title.replace('"', '\\"')
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display dialog "{escaped}" with title "{escaped_title}" buttons {{"OK"}} default button "OK"',
            ],
            check=False,
        )
    except Exception:
        pass


def set_app_user_model_id(app_id: str) -> None:
    _ = app_id


def frozen_module_cmd(module: str) -> list[str]:
    if not getattr(sys, "frozen", False):
        if module.endswith("detector.service"):
            return [sys.executable, "-m", "meetrec", "detector"]
        if module.endswith("recorder.service"):
            return [sys.executable, "-m", "meetrec", "recorder"]
        return [sys.executable, "-m", module]
    if module.endswith("detector.service"):
        return [sys.executable, "detector"]
    if module.endswith("recorder.service"):
        return [sys.executable, "recorder"]
    return [sys.executable, "-m", module]


def app_icon_path(resources_dir: str) -> str:
    icns = os.path.join(resources_dir, "meetrec.icns")
    if os.path.isfile(icns):
        return icns
    return os.path.join(resources_dir, "logo.png")


def executable_name_matches(name: str | None) -> bool:
    lowered = (name or "").lower()
    return "meetrec" in lowered or "python" in lowered


def get_scoring_weights() -> dict[str, int]:
    return {
        "mic_active": 30,
        "loopback_active": 25,
        "meeting_app_capture_active": 0,
        "meeting_app_render_active": 0,
        "meeting_app_network_active": 30,
        "in_call_title": 30,
        "known_meeting_app_running": 20,
        "known_meeting_app_foreground": 25,
        "title_hint": 15,
        "browser_meeting_context": 45,
    }
