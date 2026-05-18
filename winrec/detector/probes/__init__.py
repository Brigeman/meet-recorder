def probe_audio_activity():
    from winrec.detector.probes.audio import probe_audio_activity as _fn

    return _fn()


def probe_browser_meeting():
    from winrec.detector.probes.browser import probe_browser_meeting as _fn

    return _fn()


def probe_foreground():
    from winrec.detector.probes.foreground import probe_foreground as _fn

    return _fn()


def probe_meeting_app_network(meeting_pids):
    from winrec.detector.probes.network import probe_meeting_app_network as _fn

    return _fn(meeting_pids)


def probe_running_apps():
    from winrec.detector.probes.processes import probe_running_apps as _fn

    return _fn()

__all__ = [
    "probe_audio_activity",
    "probe_browser_meeting",
    "probe_foreground",
    "probe_meeting_app_network",
    "probe_running_apps",
]
