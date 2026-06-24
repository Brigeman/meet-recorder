"""Ensure audio probe module imports without AudioSessionState enum."""

import sys

import pytest

pytest.importorskip("comtypes")


@pytest.mark.skipif(sys.platform != "win32", reason="WASAPI probes are Windows-only")
def test_audio_module_imports():
    from meetrec.detector.probes import audio  # noqa: F401

    assert audio.SESSION_ACTIVE == 1
