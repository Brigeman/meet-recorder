import pytest

pytest.importorskip("comtypes")
pytest.importorskip("pycaw")

from meetrec.detector.probes import audio


def test_probe_meeting_app_audio_reports_active(monkeypatch):
    monkeypatch.setattr(audio, "CoCreateInstance", lambda *args, **kwargs: object())
    calls = []

    def fake_probe(**kwargs):
        flow_hint = len(calls)
        calls.append(kwargs)
        if flow_hint == 0:
            return True, 0.23
        return False, 0.01

    monkeypatch.setattr(audio, "_probe_endpoint_sessions_on_device", fake_probe)
    monkeypatch.setattr(audio, "_iter_audio_endpoints", lambda _enumerator, _flow: [object(), object()])

    cap, ren, cap_peak, ren_peak = audio.probe_meeting_app_audio({111, 222})
    assert cap is True
    assert ren is False
    assert cap_peak == 0.23
    assert ren_peak == 0.01
