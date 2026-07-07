"""Global audio activity probes on macOS via CoreAudio (no mic capture)."""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import struct
import time
from functools import lru_cache

log = logging.getLogger(__name__)

_MIC_CACHE_SECONDS = 1.0
_mic_cache: tuple[float, bool] = (0.0, False)


def _fourcc(value: bytes) -> int:
    return struct.unpack(">I", value.ljust(4, b"\0")[:4])[0]


_kAudioObjectSystemObject = 1
_kAudioHardwarePropertyDefaultInputDevice = _fourcc(b"dIn ")
_kAudioHardwarePropertyDefaultOutputDevice = _fourcc(b"dOut")
_kAudioHardwarePropertyDevices = _fourcc(b"dev#")
_kAudioObjectPropertyName = _fourcc(b"lnam")
_kAudioDevicePropertyDeviceIsRunningSomewhere = _fourcc(b"gone")
_kAudioObjectPropertyScopeGlobal = 0
_kAudioObjectPropertyElementMain = 0

MEETING_AUDIO_DEVICE_HINTS: list[tuple[str, str]] = [
    ("microsoft teams audio", "Microsoft Teams"),
    ("teams audio", "Microsoft Teams"),
    ("zoomaudio", "Zoom"),
    ("zoom audio", "Zoom"),
]


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
    lib.AudioObjectGetPropertyDataSize.argtypes = [
        ctypes.c_uint32,
        ctypes.POINTER(AudioObjectPropertyAddress),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    lib.AudioObjectGetPropertyDataSize.restype = ctypes.c_int32
    return lib


def _load_corefoundation():
    lib = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
    lib.CFStringGetCString.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_long,
        ctypes.c_uint32,
    ]
    lib.CFStringGetCString.restype = ctypes.c_bool
    lib.CFStringGetLength.argtypes = [ctypes.c_void_p]
    lib.CFStringGetLength.restype = ctypes.c_long
    return lib


def _cfstring_to_str(corefoundation, cf_ref: ctypes.c_void_p) -> str:
    if not cf_ref.value:
        return ""
    length = corefoundation.CFStringGetLength(cf_ref)
    buffer = ctypes.create_string_buffer(length * 4 + 1)
    corefoundation.CFStringGetCString(cf_ref, buffer, len(buffer), 0x08000100)
    return buffer.value.decode("utf-8", errors="replace")


@lru_cache(maxsize=1)
def _get_coreaudio():
    return _load_coreaudio()


@lru_cache(maxsize=1)
def _get_corefoundation():
    return _load_corefoundation()


def warmup_audio_probes() -> None:
    """Load CoreAudio once at detector startup — avoids cold-start cost on first tick."""
    try:
        _get_coreaudio()
        _get_corefoundation()
        _probe_input_in_use()
    except Exception as exc:
        log.debug("audio probe warmup failed: %s", exc)


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


def _list_device_ids(coreaudio) -> list[int]:
    addr = AudioObjectPropertyAddress(
        _kAudioHardwarePropertyDevices,
        _kAudioObjectPropertyScopeGlobal,
        _kAudioObjectPropertyElementMain,
    )
    data_size = ctypes.c_uint32(0)
    err = coreaudio.AudioObjectGetPropertyDataSize(
        _kAudioObjectSystemObject,
        ctypes.byref(addr),
        0,
        None,
        ctypes.byref(data_size),
    )
    if err != 0 or data_size.value == 0:
        return []
    count = data_size.value // ctypes.sizeof(ctypes.c_uint32)
    device_ids = (ctypes.c_uint32 * count)()
    err = coreaudio.AudioObjectGetPropertyData(
        _kAudioObjectSystemObject,
        ctypes.byref(addr),
        0,
        None,
        ctypes.byref(data_size),
        device_ids,
    )
    if err != 0:
        return []
    return [int(device_ids[i]) for i in range(count)]


def _device_name(coreaudio, corefoundation, device_id: int) -> str:
    addr = AudioObjectPropertyAddress(
        _kAudioObjectPropertyName,
        _kAudioObjectPropertyScopeGlobal,
        _kAudioObjectPropertyElementMain,
    )
    cf_name = ctypes.c_void_p()
    size = ctypes.c_uint32(ctypes.sizeof(cf_name))
    err = coreaudio.AudioObjectGetPropertyData(
        device_id,
        ctypes.byref(addr),
        0,
        None,
        ctypes.byref(size),
        ctypes.byref(cf_name),
    )
    if err != 0:
        return ""
    return _cfstring_to_str(corefoundation, cf_name)


def _list_named_devices() -> list[tuple[int, str]]:
    try:
        coreaudio = _get_coreaudio()
        corefoundation = _get_corefoundation()
    except Exception as exc:
        log.debug("mac audio device list init failed: %s", exc)
        return []
    devices: list[tuple[int, str]] = []
    for device_id in _list_device_ids(coreaudio):
        name = _device_name(coreaudio, corefoundation, device_id)
        if name:
            devices.append((device_id, name))
    return devices


def _device_is_running_somewhere(coreaudio, device_id: int) -> bool:
    """True when any client (Teams, browser, etc.) is using the device — no mic open needed."""
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


def probe_meeting_audio_devices() -> str | None:
    """Return meeting app when the system default route uses its virtual device."""
    try:
        coreaudio = _get_coreaudio()
        corefoundation = _get_corefoundation()
    except Exception as exc:
        log.debug("meeting audio device probe init failed: %s", exc)
        return None

    for selector in (_kAudioHardwarePropertyDefaultInputDevice, _kAudioHardwarePropertyDefaultOutputDevice):
        device_id = _default_device(coreaudio, selector)
        if not device_id:
            continue
        lowered = _device_name(coreaudio, corefoundation, device_id).lower()
        for hint, app in MEETING_AUDIO_DEVICE_HINTS:
            if hint in lowered:
                return app
    return None


def is_mic_active() -> bool:
    """Return whether the default input device is in use (cached ~1 s)."""
    return _probe_input_in_use()


def _probe_input_in_use() -> bool:
    """Detect mic use via CoreAudio — never opens our own capture stream."""
    global _mic_cache
    now = time.time()
    if now - _mic_cache[0] < _MIC_CACHE_SECONDS:
        return _mic_cache[1]

    active = False
    try:
        coreaudio = _get_coreaudio()
        device_id = _default_device(coreaudio, _kAudioHardwarePropertyDefaultInputDevice)
        if device_id:
            active = _device_is_running_somewhere(coreaudio, device_id)
    except Exception as exc:
        log.debug("mac input-in-use probe failed: %s", exc)

    _mic_cache = (now, active)
    return active


def _probe_output_in_use() -> bool:
    """Detect whether the default output device is actively playing audio."""
    try:
        coreaudio = _get_coreaudio()
        device_id = _default_device(coreaudio, _kAudioHardwarePropertyDefaultOutputDevice)
        if not device_id:
            return False
        return _device_is_running_somewhere(coreaudio, device_id)
    except Exception as exc:
        log.debug("mac output-in-use probe failed: %s", exc)
        return False


def probe_audio_activity() -> tuple[bool, bool]:
    if probe_meeting_audio_devices():
        return True, True

    mic = _probe_input_in_use()
    loopback = _probe_output_in_use()
    return mic, loopback


def probe_meeting_app_audio(meeting_pids: set[int]) -> tuple[bool, bool, float, float]:
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
