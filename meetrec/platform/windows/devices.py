"""WASAPI device selection for loopback and microphone capture."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def _wasapi_info(p: Any) -> dict[str, Any]:
    import pyaudiowpatch as pyaudio

    return p.get_host_api_info_by_type(pyaudio.paWASAPI)


def default_output_key(p: Any) -> tuple[int, str] | None:
    try:
        info = _wasapi_info(p)
        idx = int(info["defaultOutputDevice"])
        if idx < 0:
            return None
        dev = p.get_device_info_by_index(idx)
        return idx, str(dev.get("name", ""))
    except (OSError, ValueError, KeyError):
        return None


def default_input_key(p: Any) -> tuple[int, str] | None:
    try:
        info = _wasapi_info(p)
        idx = int(info["defaultInputDevice"])
        if idx < 0:
            return None
        dev = p.get_device_info_by_index(idx)
        return idx, str(dev.get("name", ""))
    except (OSError, ValueError, KeyError):
        return None


def _find_loopback_by_name(p: Any, default_speakers: dict[str, Any]) -> dict[str, Any] | None:
    speaker_name = str(default_speakers.get("name", ""))
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev.get("isLoopbackDevice") and speaker_name in str(dev.get("name", "")):
            return dev
    return None


def _find_any_loopback(p: Any) -> dict[str, Any] | None:
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev.get("isLoopbackDevice"):
            return dev
    return None


def find_loopback_device(p: Any) -> dict[str, Any]:
    getter = getattr(p, "get_default_wasapi_loopback", None)
    if callable(getter):
        try:
            dev = getter()
            if dev:
                log.debug("loopback via get_default_wasapi_loopback: %s", dev.get("name"))
                return dev
        except (OSError, RuntimeError) as exc:
            log.debug("get_default_wasapi_loopback failed: %s", exc)

    try:
        wasapi = _wasapi_info(p)
        default_speakers = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
        by_name = _find_loopback_by_name(p, default_speakers)
        if by_name:
            log.debug("loopback via name match: %s", by_name.get("name"))
            return by_name
    except (OSError, ValueError, KeyError) as exc:
        log.debug("loopback name match failed: %s", exc)

    fallback = _find_any_loopback(p)
    if fallback:
        log.warning("loopback fallback to first device: %s", fallback.get("name"))
        return fallback

    raise RuntimeError("No WASAPI loopback device found")


def find_mic_device(p: Any) -> dict[str, Any] | None:
    try:
        wasapi = _wasapi_info(p)
        idx = int(wasapi["defaultInputDevice"])
        if idx < 0:
            return None
        return p.get_device_info_by_index(idx)
    except (OSError, ValueError, KeyError) as exc:
        log.debug("find_mic_device failed: %s", exc)
        return None
