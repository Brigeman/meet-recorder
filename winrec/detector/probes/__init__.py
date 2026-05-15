from winrec.detector.probes.audio import probe_audio_activity
from winrec.detector.probes.browser import probe_browser_meeting
from winrec.detector.probes.foreground import probe_foreground
from winrec.detector.probes.processes import probe_running_apps

__all__ = [
    "probe_audio_activity",
    "probe_browser_meeting",
    "probe_foreground",
    "probe_running_apps",
]
