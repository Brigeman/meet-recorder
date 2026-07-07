"""Path-selection + fallback glue for capture-time VoiceProcessingIO AEC.

The Swift helper itself cannot be unit-tested here, so these tests exercise the
Python integration: how ``AudioCapture`` chooses the native OS-AEC mic vs. the
plain sounddevice mic, and that it always falls back cleanly.
"""

import queue
import sys
import threading
import types

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS VoiceProcessingIO capture"
)

from meetrec.platform.macos import capture as cap
from meetrec.platform.macos.capture import CHUNK, FILE_RATE, AudioCapture, StreamBundle


def _fake_sounddevice(on_input_stream=None):
    """Minimal stand-in for the sounddevice module used inside _open_streams."""
    mod = types.ModuleType("sounddevice")

    def query_devices(kind=None):
        return {
            "default_samplerate": 44100,
            "max_input_channels": 1,
            "name": "FakeMic",
        }

    class FakeStream:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.started = False
            if on_input_stream is not None:
                on_input_stream(kwargs)

        def start(self):
            self.started = True

        def stop(self):
            pass

        def close(self):
            pass

    mod.query_devices = query_devices
    mod.InputStream = FakeStream
    return mod


def _write_helper(path, py_code):
    # /bin/sh wrapper so the interpreter path (which may contain spaces) is quoted,
    # avoiding shebang word-splitting/length limits.
    path.write_text(f'#!/bin/sh\nexec "{sys.executable}" -c \'{py_code}\'\n')
    path.chmod(0o755)
    return path


def test_want_native_mic_reflects_flag_and_defaults_off():
    assert AudioCapture({"mic_os_aec": True})._want_native_mic() is True
    assert AudioCapture({"mic_os_aec": False})._want_native_mic() is False
    # Absent key must default to False (safe): never opt in silently.
    assert AudioCapture({})._want_native_mic() is False


def test_mic_helper_path_finds_built_binary():
    """The VoiceProcessingIO helper must be discoverable once built."""
    path = cap._mic_helper_path()
    assert path is not None, "MeetRecVoiceMic not built; run helper/build.sh"
    assert path.name == "MeetRecVoiceMic"
    assert path.is_file()


def test_start_native_mic_streams_frames(tmp_path, monkeypatch):
    helper = _write_helper(
        tmp_path / "MeetRecVoiceMic",
        "import sys, time; "
        'sys.stderr.write("READY voiceio\\n"); sys.stderr.flush(); '
        f"sys.stdout.buffer.write(bytes([1, 2]) * {CHUNK}); sys.stdout.buffer.flush(); "
        "time.sleep(5)",
    )
    monkeypatch.setattr(cap, "_mic_helper_path", lambda: helper)

    ac = AudioCapture({"mic_os_aec": True})
    mic_queue: queue.Queue = queue.Queue()
    mic_error = threading.Event()
    first_frame = threading.Event()

    proc = ac._start_native_mic(mic_queue, mic_error, first_frame)
    try:
        assert proc is not None
        assert first_frame.is_set()
        frame = mic_queue.get(timeout=2.0)
        assert isinstance(frame, np.ndarray)
        assert frame.dtype == np.int16
        assert len(frame) == CHUNK
        assert not mic_error.is_set()
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                proc.kill()


def test_start_native_mic_falls_back_when_helper_missing(monkeypatch):
    monkeypatch.setattr(cap, "_mic_helper_path", lambda: None)
    ac = AudioCapture({"mic_os_aec": True})
    result = ac._start_native_mic(queue.Queue(), threading.Event(), threading.Event())
    assert result is None


def test_start_native_mic_falls_back_when_no_audio(tmp_path, monkeypatch):
    """Helper that never emits audio must be torn down and trigger fallback."""
    helper = _write_helper(tmp_path / "MeetRecVoiceMic", "import time; time.sleep(30)")
    monkeypatch.setattr(cap, "_mic_helper_path", lambda: helper)
    ac = AudioCapture({"mic_os_aec": True})
    result = ac._start_native_mic(queue.Queue(), threading.Event(), threading.Event())
    assert result is None


def test_start_native_mic_falls_back_on_silent_frames(tmp_path, monkeypatch):
    helper = _write_helper(
        tmp_path / "MeetRecVoiceMic",
        "import sys, time; "
        'sys.stderr.write("READY voiceio rate=48000 ch=1\\n"); sys.stderr.flush(); '
        f"sys.stdout.buffer.write(bytes([0, 0]) * {CHUNK * 5}); sys.stdout.buffer.flush(); "
        "time.sleep(5)",
    )
    monkeypatch.setattr(cap, "_mic_helper_path", lambda: helper)
    ac = AudioCapture({"mic_os_aec": True})
    result = ac._start_native_mic(queue.Queue(), threading.Event(), threading.Event())
    assert result is None


def test_start_native_mic_falls_back_on_multichannel(tmp_path, monkeypatch):
    helper = _write_helper(
        tmp_path / "MeetRecVoiceMic",
        "import sys, time; "
        'sys.stderr.write("READY voiceio rate=48000 ch=9\\n"); sys.stderr.flush(); '
        f"sys.stdout.buffer.write(bytes([1, 2]) * {CHUNK}); sys.stdout.buffer.flush(); "
        "time.sleep(5)",
    )
    monkeypatch.setattr(cap, "_mic_helper_path", lambda: helper)
    ac = AudioCapture({"mic_os_aec": True})
    result = ac._start_native_mic(queue.Queue(), threading.Event(), threading.Event())
    assert result is None


def test_open_streams_selects_native_and_skips_sounddevice(monkeypatch):
    # No system-audio helper so we don't launch the real ScreenCaptureKit process.
    monkeypatch.setattr(cap, "_helper_path", lambda: None)
    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        _fake_sounddevice(
            on_input_stream=lambda kw: pytest.fail("sounddevice mic opened despite native AEC")
        ),
    )
    ac = AudioCapture({"mic_os_aec": True, "speaker_separation": True})
    sentinel = object()
    monkeypatch.setattr(ac, "_start_native_mic", lambda q, e, f: sentinel)

    bundle = ac._open_streams()
    try:
        assert bundle.mic_native is True
        assert bundle.mic_stream is None
        assert bundle.mic_rate == FILE_RATE
        assert bundle.mic_ch == 1
        assert bundle.mic_helper_proc is sentinel
    finally:
        bundle.mic_helper_proc = None  # sentinel is not a real proc
        ac._close_bundle(bundle)


def test_open_streams_falls_back_to_sounddevice(monkeypatch):
    monkeypatch.setattr(cap, "_helper_path", lambda: None)
    created: dict = {}
    monkeypatch.setitem(
        sys.modules, "sounddevice", _fake_sounddevice(on_input_stream=created.update)
    )
    ac = AudioCapture({"mic_os_aec": True})
    monkeypatch.setattr(ac, "_start_native_mic", lambda q, e, f: None)

    bundle = ac._open_streams()
    try:
        assert bundle.mic_native is False
        assert bundle.mic_stream is not None
        assert bundle.mic_name == "FakeMic"
        assert created, "sounddevice InputStream was not opened on fallback"
    finally:
        ac._close_bundle(bundle)


def test_record_device_writes_native_flag_to_metadata():
    ac = AudioCapture({})
    ac._metadata = {"devices_used": []}
    bundle = StreamBundle(
        helper_proc=None,
        mic_stream=None,
        mic_rate=FILE_RATE,
        mic_ch=1,
        mic_name="VoiceProcessingIO (native AEC)",
        system_available=True,
        mic_helper_proc=object(),
        mic_native=True,
    )
    ac._record_device(bundle)
    assert ac._metadata["mic_os_aec_active"] is True
    assert ac._metadata["devices_used"][0]["mic_os_aec"] is True


def test_process_chunk_native_mic_skips_export_side_bleed_subtraction():
    """When the mic is already echo-cancelled, the capture path must not run the
    (useless-on-real-echo) single-tap subtraction on top of it."""
    ac = AudioCapture({"echo_cancellation": True})

    def _boom(*_a, **_k):
        raise AssertionError("single-tap AEC ran on an already-clean native mic")

    ac._bleed_state.update = _boom  # type: ignore[method-assign]
    bundle = StreamBundle(
        helper_proc=None,
        mic_stream=None,
        mic_rate=FILE_RATE,
        mic_ch=1,
        mic_name="VoiceProcessingIO (native AEC)",
        system_available=True,
        mic_native=True,
    )
    lb_bytes = np.zeros(CHUNK * 2, dtype=np.int16).tobytes()  # stereo loopback frame
    mic = (np.random.default_rng(0).standard_normal(CHUNK) * 3000).astype(np.int16)
    out = ac._process_chunk(bundle, lb_bytes, mic, dual_track=False)
    assert out.dtype == np.int16
    assert out.size > 0
