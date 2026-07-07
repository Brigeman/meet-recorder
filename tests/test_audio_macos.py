import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS CoreAudio")

from meetrec.platform.macos import audio as mac_audio


def test_probe_audio_activity_does_not_import_sounddevice(monkeypatch):
    """Detector must not open sd.rec — that triggers the macOS mic privacy banner."""
    import importlib

    def _blocked(name, *args, **kwargs):
        if name == "sounddevice":
            raise ImportError("sounddevice must not be used for activity probes")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr("builtins.__import__", _blocked)
    importlib.reload(mac_audio)
    mic, loopback = mac_audio.probe_audio_activity()
    assert isinstance(mic, bool)
    assert isinstance(loopback, bool)


def test_fourcc_running_somewhere_selector():
    assert mac_audio._fourcc(b"gone") == mac_audio._kAudioDevicePropertyDeviceIsRunningSomewhere
