"""Recorder package — lazy export of AudioCapture to avoid heavy imports in tests."""

from __future__ import annotations

__all__ = ["AudioCapture"]


def __getattr__(name: str):
    if name == "AudioCapture":
        from winrec.recorder.capture import AudioCapture

        return AudioCapture
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
