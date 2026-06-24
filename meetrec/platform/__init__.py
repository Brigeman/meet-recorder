"""Select platform adapter at import time."""

from __future__ import annotations

import sys

if sys.platform == "win32":
    from meetrec.platform.windows import adapter as _impl
elif sys.platform == "darwin":
    from meetrec.platform.macos import adapter as _impl
else:
    from meetrec.platform.linux import adapter as _impl

APP_ID = _impl.APP_ID
BROWSER_PROCESSES = _impl.BROWSER_PROCESSES
CONFIG_DIR = _impl.CONFIG_DIR
CONFIG_FILE = _impl.CONFIG_FILE
LEGACY_CONFIG_DIR = _impl.LEGACY_CONFIG_DIR
LEGACY_SETTINGS = _impl.LEGACY_SETTINGS
LOCK_FILE = _impl.LOCK_FILE
DEFAULT_RECORDINGS_DIR = _impl.DEFAULT_RECORDINGS_DIR

AudioCapture = _impl.AudioCapture

probe_foreground = _impl.probe_foreground
probe_audio_activity = _impl.probe_audio_activity
probe_meeting_app_audio = _impl.probe_meeting_app_audio
probe_browser_meeting = _impl.probe_browser_meeting
mic_used_by_meeting_process = _impl.mic_used_by_meeting_process

resolve_app_for_pid = _impl.resolve_app_for_pid
list_running_meeting_apps = _impl.list_running_meeting_apps
list_running_meeting_pids = _impl.list_running_meeting_pids
match_title_hint = _impl.match_title_hint
match_in_call_title = _impl.match_in_call_title

autostart_is_supported = _impl.autostart_is_supported
autostart_current_executable_path = _impl.autostart_current_executable_path
autostart_get_registered_path = _impl.autostart_get_registered_path
autostart_is_enabled = _impl.autostart_is_enabled
autostart_enable = _impl.autostart_enable
autostart_disable = _impl.autostart_disable

ensure_native_init = _impl.ensure_native_init
open_path = _impl.open_path
show_message = _impl.show_message
set_app_user_model_id = _impl.set_app_user_model_id
frozen_module_cmd = _impl.frozen_module_cmd
app_icon_path = _impl.app_icon_path
executable_name_matches = _impl.executable_name_matches
get_scoring_weights = _impl.get_scoring_weights

__all__ = [
    "APP_ID",
    "AudioCapture",
    "BROWSER_PROCESSES",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "DEFAULT_RECORDINGS_DIR",
    "LEGACY_CONFIG_DIR",
    "LEGACY_SETTINGS",
    "LOCK_FILE",
    "app_icon_path",
    "autostart_current_executable_path",
    "autostart_disable",
    "autostart_enable",
    "autostart_get_registered_path",
    "autostart_is_enabled",
    "autostart_is_supported",
    "ensure_native_init",
    "executable_name_matches",
    "frozen_module_cmd",
    "get_scoring_weights",
    "list_running_meeting_apps",
    "list_running_meeting_pids",
    "match_in_call_title",
    "match_title_hint",
    "mic_used_by_meeting_process",
    "open_path",
    "probe_audio_activity",
    "probe_browser_meeting",
    "probe_foreground",
    "probe_meeting_app_audio",
    "resolve_app_for_pid",
    "set_app_user_model_id",
    "show_message",
]
