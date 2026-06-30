"""Global audio activity probes on macOS via CoreAudio."""

from __future__ import annotations

import ctypes
import ctypes.util
import logging

log = logging.getLogger(__name__)

_kAudioObjectSystemObject = 1
_kAudioHardwarePropertyDefaultInputDevice = 0x75696E64
_kAudioHardwarePropertyDefaultOutputDevice = 0x646F7574
_kAudioDevicePropertyDeviceIsRunningSomewhere = 0x64697372
_kAudioObjectPropertyScopeGlobal = 0x676C6F62
_kAudioObjectPropertyElementMain = 0


class AudioObjectPropertyAddress(ctypes.Structure):
    _fields_ = [
        ("mSelector", ctypes.c_uint32),
        ("mScope", ctypes.c_uint32),
        ("mElement", ctypes.c_uint32),
    ]


def _load_coreaudio():
    path = ctypes.util.find_library("CoreAudio")
    if not path:
        raise OSError("CoreAudio library not found")
    lib = ctypes.CDLL(path)
    lib.AudioObjectGetPropertyData.argtypes = [
        ctypes.c_uint32,
        ctypes.POINTER(AudioObjectPropertyAddress),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    ]
    lib.AudioObjectGetPropertyData.restype = ctypes.c_int32
    return lib


def _default_device(coreaudio, selector: int) -> int | None:
    addr = AudioObjectPropertyAddress(selector, _kAudioObjectPropertyScopeGlobal, 0)
    device_id = ctypes.c_uint32(0)
    size = ctypes.c_uint32(ctypes.sizeof(device_id))
    err = coreaudio.AudioObjectGetPropertyData(
        _kAudioObjectSystemObject,
        ctypes.byref(addr),
        0,
        None,
        ctypes.byref(size),
        ctypes.byref(device_id),
    )
    if err != 0:
        return None
    return int(device_id.value)


def _device_is_running(coreaudio, device_id: int) -> bool:
    addr = AudioObjectPropertyAddress(
        _kAudioDevicePropertyDeviceIsRunningSomewhere,
        _kAudioObjectPropertyScopeGlobal,
        _kAudioObjectPropertyElementMain,
    )
    running = ctypes.c_uint32(0)
    size = ctypes.c_uint32(ctypes.sizeof(running))
    err = coreaudio.AudioObjectGetPropertyData(
        device_id,
        ctypes.byref(addr),
        0,
        None,
        ctypes.byref(size),
        ctypes.byref(running),
    )
    if err != 0:
        return False
    return bool(running.value)


def probe_audio_activity() -> tuple[bool, bool]:
    mic = False
    loopback = False
    try:
        coreaudio = _load_coreaudio()
        input_id = _default_device(coreaudio, _kAudioHardwarePropertyDefaultInputDevice)
        output_id = _default_device(coreaudio, _kAudioHardwarePropertyDefaultOutputDevice)
        if input_id is not None:
            mic = _device_is_running(coreaudio, input_id)
        if output_id is not None:
            loopback = _device_is_running(coreaudio, output_id)
    except Exception as exc:
        log.debug("mac audio probe failed: %s", exc)
    return mic, loopback


def probe_meeting_app_audio(meeting_pids: set[int]) -> tuple[bool, bool, float, float]:
    # Deferred: CoreAudio process taps / ScreenCaptureKit per-app audio are not implemented yet.
    # Detection on macOS relies on global mic+loopback (probe_audio_activity) plus app/title context.
    _ = meeting_pids
    return False, False, 0.0, 0.0


def mic_used_by_meeting_process() -> bool:
    mic, _ = probe_audio_activity()
    if not mic:
        return False
    try:
        import psutil

        from meetrec.platform.macos.apps import BROWSER_NAMES, PROCESS_TO_APP, _normalize_name

        for proc in psutil.process_iter(["name"]):
            name = _normalize_name(proc.info.get("name"))
            if name in PROCESS_TO_APP or name in BROWSER_NAMES:
                return True
    except Exception:
        return mic
    return False
