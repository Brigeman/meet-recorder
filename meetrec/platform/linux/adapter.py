"""Linux CI stub adapter — allows pytest on ubuntu-latest."""

from __future__ import annotations

import sys

from meetrec.detector.titles import match_in_call_title, match_title_hint
from meetrec.platform.linux import paths

APP_ID = paths.APP_ID
BROWSER_PROCESSES = paths.BROWSER_PROCESSES
CONFIG_DIR = paths.CONFIG_DIR
CONFIG_FILE = paths.CONFIG_FILE
LEGACY_CONFIG_DIR = paths.LEGACY_CONFIG_DIR
LEGACY_SETTINGS = paths.LEGACY_SETTINGS
LOCK_FILE = paths.LOCK_FILE
DEFAULT_RECORDINGS_DIR = paths.DEFAULT_RECORDINGS_DIR


class AudioCapture:
    def __init__(self, settings: dict):
        self._settings = settings

    def update_settings(self, settings: dict) -> None:
        self._settings = settings

    @property
    def is_recording(self) -> bool:
        return False

    @property
    def current_file(self) -> str | None:
        return None

    @property
    def metadata(self) -> dict:
        return {}

    @property
    def peak(self) -> float:
        return 0.0

    def set_peak_callback(self, cb) -> None:
        return None

    def build_output_path(self, app: str, session_id: str) -> str:
        return ""

    def start(self, session_id: str, app: str, matched=None, meeting_hint=None) -> str:
        raise RuntimeError("Recording is not supported on Linux")

    def stop(self) -> dict:
        return {}


def probe_foreground() -> tuple[str | None, str]:
    return None, ""


def probe_audio_activity() -> tuple[bool, bool]:
    return False, False


def probe_meeting_app_audio(meeting_pids: set[int]) -> tuple[bool, bool, float, float]:
    _ = meeting_pids
    return False, False, 0.0, 0.0


def probe_browser_meeting() -> tuple[bool, str | None, str, int]:
    return False, None, "", 0


def mic_used_by_meeting_process() -> bool:
    return False


def resolve_app_for_pid(pid: int) -> str | None:
    _ = pid
    return None


def list_running_meeting_apps() -> set[str]:
    return set()


def list_running_meeting_pids() -> dict[str, list[int]]:
    return {}


def autostart_is_supported() -> bool:
    return False


def autostart_current_executable_path() -> str | None:
    return None


def autostart_get_registered_path() -> str | None:
    return None


def autostart_is_enabled() -> bool:
    return False


def autostart_enable(executable: str | None = None) -> bool:
    _ = executable
    return False


def autostart_disable() -> bool:
    return False


def ensure_native_init() -> None:
    return None


def open_path(path: str) -> None:
    _ = path


def show_message(message: str, title: str, flags: int = 0) -> None:
    _ = message, title, flags


def set_app_user_model_id(app_id: str) -> None:
    _ = app_id


def frozen_module_cmd(module: str) -> list[str]:
    if module.endswith("detector.service"):
        return [sys.executable, "-m", "meetrec", "detector"]
    if module.endswith("recorder.service"):
        return [sys.executable, "-m", "meetrec", "recorder"]
    return [sys.executable, "-m", module]


def app_icon_path(resources_dir: str) -> str:
    import os

    return os.path.join(resources_dir, "logo.png")


def executable_name_matches(name: str | None) -> bool:
    lowered = (name or "").lower()
    return "meetrec" in lowered or "python" in lowered


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
