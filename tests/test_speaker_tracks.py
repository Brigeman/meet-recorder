import tempfile
import wave
from pathlib import Path

import numpy as np

from meetrec.recorder.audio_mix import interleave_stereo
from meetrec.recorder.speaker_tracks import export_speaker_tracks, finalize_recording_metadata


def test_export_speaker_tracks_splits_stereo_and_mixed():
    lb = np.array([10000, 5000, -5000], dtype=np.int16)
    mic = np.array([7000, 3500, -3500], dtype=np.int16)
    stereo = interleave_stereo(lb, mic)

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "call.wav")
        with wave.open(path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(stereo.tobytes())

        export = export_speaker_tracks(path)
        assert export is not None
        assert Path(export.remote_path).is_file()
        assert Path(export.local_path).is_file()
        assert Path(export.mixed_path).is_file()
        assert export.speakers[0]["id"] == "remote"
        assert export.speakers[1]["id"] == "local"


def test_export_gated_mixed_prefers_remote_on_echo_only():
    lag = 144  # 3 ms
    n = 4800
    lb = (np.sin(np.linspace(0, 40 * np.pi, n)) * 8000).astype(np.int16)
    mic = np.zeros(n, dtype=np.int16)
    mic[lag:] = (lb[:-lag].astype(np.float64) * 0.75).astype(np.int16)
    stereo = interleave_stereo(lb, mic)

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "echo.wav")
        with wave.open(path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(stereo.tobytes())

        export = export_speaker_tracks(path)
        assert export is not None

        import wave as wave_mod

        with wave_mod.open(export.mixed_path, "rb") as wf:
            mixed = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float64)
        with wave_mod.open(export.remote_path, "rb") as wf:
            remote = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float64)

        def remote_bleed(mixed, remote):
            energy = float(np.dot(remote, remote))
            return float(np.dot(mixed, remote)) / energy if energy > 1e6 else 0.0

        assert remote_bleed(mixed, remote) <= 1.15


def test_export_native_aec_passes_mic_through_without_subtraction():
    """With native AEC, the export must NOT run single-tap AEC: _local == raw mic (R)."""
    lag = 144
    n = 4800
    lb = (np.sin(np.linspace(0, 40 * np.pi, n)) * 8000).astype(np.int16)
    mic = np.zeros(n, dtype=np.int16)
    mic[lag:] = (lb[:-lag].astype(np.float64) * 0.75).astype(np.int16)
    stereo = interleave_stereo(lb, mic)

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "native.wav")
        with wave.open(path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(stereo.tobytes())

        export = export_speaker_tracks(path, native_aec=True)
        assert export is not None

        with wave.open(export.local_path, "rb") as wf:
            local = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        # mic (R channel) is passed straight through as the local voice
        assert np.array_equal(local, mic[: len(local)])


def test_finalize_uses_native_flag_from_metadata(monkeypatch):
    import meetrec.recorder.speaker_tracks as st

    captured = {}

    def fake_export(path, *, native_aec=False):
        captured["native_aec"] = native_aec
        return None

    monkeypatch.setattr(st, "export_speaker_tracks", fake_export)
    st.finalize_recording_metadata({"mic_os_aec_active": True}, "/tmp/x.wav", enabled=True)
    assert captured["native_aec"] is True

    captured.clear()
    st.finalize_recording_metadata({"mic_os_aec_active": False}, "/tmp/x.wav", enabled=True)
    assert captured["native_aec"] is False


def test_finalize_promotes_mixed_to_primary_wav():
    n = 4800
    lb = (np.sin(np.linspace(0, 40 * np.pi, n)) * 8000).astype(np.int16)
    mic = np.zeros(n, dtype=np.int16)
    stereo = interleave_stereo(lb, mic)

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "call.wav")
        with wave.open(path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(stereo.tobytes())

        metadata: dict = {}
        finalize_recording_metadata(metadata, path, enabled=True)

        with wave.open(path, "rb") as wf:
            assert wf.getnchannels() == 1
        assert Path(metadata["stereo_file"]).name == "call_stereo.wav"
        assert metadata["audio_file"] == path
        assert Path(metadata["mixed_file"]).is_file()
