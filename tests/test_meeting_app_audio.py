import pytest

pytest.importorskip("comtypes")
pytest.importorskip("pycaw")

from winrec.detector.probes import audio


def test_probe_meeting_app_audio_reports_active(monkeypatch):
    monkeypatch.setattr(audio, "CoCreateInstance", lambda *args, **kwargs: object())

    calls = []

    def fake_probe(enumerator, flow, meeting_pids):
        calls.append((flow, set(meeting_pids)))
        if flow == 1:
            return True, 0.23
        return False, 0.01

    monkeypatch.setattr(audio, "_probe_endpoint_sessions", fake_probe)

    cap, ren, cap_peak, ren_peak = audio.probe_meeting_app_audio({111, 222})
    assert cap is True
    assert ren is False
    assert cap_peak == 0.23
    assert ren_peak == 0.01
    assert calls[0][0] == 1
    assert calls[1][0] == 0
