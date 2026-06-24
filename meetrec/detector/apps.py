"""Platform-specific meeting app detection — delegates to active adapter."""

from meetrec.platform import (
    list_running_meeting_apps,
    list_running_meeting_pids,
    match_in_call_title,
    match_title_hint,
    resolve_app_for_pid,
)

__all__ = [
    "list_running_meeting_apps",
    "list_running_meeting_pids",
    "match_in_call_title",
    "match_title_hint",
    "resolve_app_for_pid",
]
