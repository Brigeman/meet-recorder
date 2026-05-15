"""Microphone and loopback activity probes via WASAPI."""

import logging

import psutil
from comtypes import CLSCTX_ALL, CoCreateInstance
from pycaw.constants import CLSID_MMDeviceEnumerator
from pycaw.pycaw import (
    IAudioMeterInformation,
    IAudioSessionControl2,
    IAudioSessionManager2,
    IMMDeviceEnumerator,
)

# WASAPI AudioSessionStateActive — use int for pycaw builds without AudioSessionState enum.
SESSION_ACTIVE = 1

from winrec.config import BROWSER_PROCESSES
from winrec.detector.apps import PROCESS_TO_APP, WEBVIEW2, webview2_has_valid_ancestor

log = logging.getLogger(__name__)

LOOPBACK_PEAK_THRESHOLD = 0.02
MIC_PEAK_THRESHOLD = 0.015


def probe_audio_activity() -> tuple[bool, bool]:
    mic = False
    loopback = False
    try:
        enumerator = CoCreateInstance(
            CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL
        )
        mic_active = _probe_capture_sessions(enumerator)
        loopback_active = _probe_render_peak(enumerator)
        return mic_active, loopback_active
    except Exception as e:
        log.debug("audio probe failed: %s", e)
        return mic, loopback


def _probe_capture_sessions(enumerator) -> bool:
    try:
        mic_device = enumerator.GetDefaultAudioEndpoint(1, 0)
        raw = mic_device.Activate(IAudioSessionManager2._iid_, CLSCTX_ALL, None)
        mgr = raw.QueryInterface(IAudioSessionManager2)
        session_enum = mgr.GetSessionEnumerator()
    except Exception:
        return False

    for i in range(session_enum.GetCount()):
        ctl = session_enum.GetSession(i)
        if ctl.GetState() != SESSION_ACTIVE:
            continue
        try:
            ctl2 = ctl.QueryInterface(IAudioSessionControl2)
            pid = ctl2.GetProcessId()
            if pid == 0:
                continue
            peak = _session_peak(ctl)
            if peak >= MIC_PEAK_THRESHOLD:
                return True
        except Exception:
            continue
    return False


def _probe_render_peak(enumerator) -> bool:
    try:
        render = enumerator.GetDefaultAudioEndpoint(0, 0)
        raw = render.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
        meter = raw.QueryInterface(IAudioMeterInformation)
        peak = meter.GetPeakValue()
        return peak >= LOOPBACK_PEAK_THRESHOLD
    except Exception:
        return False


def _session_peak(session_ctl) -> float:
    try:
        meter = session_ctl.QueryInterface(IAudioMeterInformation)
        return meter.GetPeakValue()
    except Exception:
        return 1.0 if session_ctl.GetState() == SESSION_ACTIVE else 0.0


def mic_used_by_meeting_process() -> bool:
    """Stronger mic signal when a known comm app holds the mic."""
    try:
        enumerator = CoCreateInstance(
            CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL
        )
        mic_device = enumerator.GetDefaultAudioEndpoint(1, 0)
        raw = mic_device.Activate(IAudioSessionManager2._iid_, CLSCTX_ALL, None)
        mgr = raw.QueryInterface(IAudioSessionManager2)
        session_enum = mgr.GetSessionEnumerator()
    except Exception:
        return False

    for i in range(session_enum.GetCount()):
        ctl = session_enum.GetSession(i)
        if ctl.GetState() != SESSION_ACTIVE:
            continue
        try:
            ctl2 = ctl.QueryInterface(IAudioSessionControl2)
            pid = ctl2.GetProcessId()
            if pid == 0:
                continue
            name = psutil.Process(pid).name().lower()
            if name in PROCESS_TO_APP or name in BROWSER_PROCESSES:
                return True
            if name == WEBVIEW2 and webview2_has_valid_ancestor(pid):
                return True
        except Exception:
            continue
    return False
