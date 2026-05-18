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


def probe_meeting_app_audio(meeting_pids: set[int]) -> tuple[bool, bool, float, float]:
    """Per-process meeting audio sessions on capture/render endpoints."""
    if not meeting_pids:
        return False, False, 0.0, 0.0
    try:
        enumerator = CoCreateInstance(
            CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL
        )
        cap_active, cap_peak = _probe_endpoint_sessions(
            enumerator=enumerator,
            flow=1,
            meeting_pids=meeting_pids,
        )
        ren_active, ren_peak = _probe_endpoint_sessions(
            enumerator=enumerator,
            flow=0,
            meeting_pids=meeting_pids,
        )
        return cap_active, ren_active, cap_peak, ren_peak
    except Exception as e:
        log.debug("meeting app audio probe failed: %s", e)
        return False, False, 0.0, 0.0


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


def _probe_endpoint_sessions(enumerator, flow: int, meeting_pids: set[int]) -> tuple[bool, float]:
    try:
        device = enumerator.GetDefaultAudioEndpoint(flow, 0)
        raw = device.Activate(IAudioSessionManager2._iid_, CLSCTX_ALL, None)
        mgr = raw.QueryInterface(IAudioSessionManager2)
        session_enum = mgr.GetSessionEnumerator()
    except Exception:
        return False, 0.0

    active = False
    peak = 0.0
    for i in range(session_enum.GetCount()):
        ctl = session_enum.GetSession(i)
        try:
            ctl2 = ctl.QueryInterface(IAudioSessionControl2)
            pid = ctl2.GetProcessId()
        except Exception:
            continue
        if pid == 0 or pid not in meeting_pids:
            continue
        if ctl.GetState() == SESSION_ACTIVE:
            active = True
        peak = max(peak, _session_peak(ctl))
    return active, peak


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
