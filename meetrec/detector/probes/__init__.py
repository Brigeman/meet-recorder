"""Detector probes — delegates to platform adapter where needed."""

from meetrec.detector.probes.network import probe_meeting_app_network
from meetrec.detector.probes.processes import probe_running_apps
from meetrec.platform import (
    probe_audio_activity,
    probe_browser_meeting,
    probe_foreground,
)

__all__ = [
    "probe_audio_activity",
    "probe_browser_meeting",
    "probe_foreground",
    "probe_meeting_app_network",
    "probe_running_apps",
]
