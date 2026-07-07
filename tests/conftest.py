"""Pytest collection guards.

macOS-only test modules import platform code (pyobjc / CoreAudio /
sounddevice / native panels) at module import time. ``skipif`` only skips
execution, not collection, so on non-macOS CI runners the import would fail
and break the whole run. Exclude those modules from collection off macOS.
"""

import sys

collect_ignore: list[str] = []

if sys.platform != "darwin":
    collect_ignore += [
        "test_apps_macos.py",
        "test_audio_macos.py",
        "test_capture_native_mic.py",
        "test_scoring_macos.py",
    ]
