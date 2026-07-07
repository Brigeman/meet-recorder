"""Recorder stop should return quickly and defer heavy export."""

from __future__ import annotations

import io
import json
import threading
import time
from unittest.mock import MagicMock

from meetrec.recorder.service import RecorderService


def test_stop_emits_stopped_then_exports_in_background(monkeypatch):
    svc = RecorderService()
    svc._session_id = "sess-1"

    meta = {
        "audio_file": "/tmp/meeting.wav",
        "speaker_separation": True,
    }
    svc._capture = MagicMock()
    svc._capture.is_recording = True
    svc._capture.current_file = "/tmp/meeting.wav"
    svc._capture.metadata = dict(meta)
    svc._capture.stop.return_value = dict(meta)

    export_started = threading.Event()

    def fake_finalize_export():
        export_started.set()

    svc._capture.finalize_export.side_effect = fake_finalize_export

    out = io.StringIO()
    monkeypatch.setattr(
        "meetrec.recorder.service.write_jsonl_line",
        lambda obj: out.write(json.dumps(obj) + "\n"),
    )

    svc._stop()

    lines = [json.loads(line) for line in out.getvalue().strip().splitlines()]
    assert lines[0]["type"] == "recording_stopped"
    assert lines[0]["export_pending"] is True
    assert svc._capture.stop.call_args.kwargs.get("defer_export") is True

    deadline = time.time() + 2.0
    while time.time() < deadline:
        payload = out.getvalue()
        if export_started.is_set() and "recording_exported" in payload:
            break
        time.sleep(0.02)

    assert export_started.is_set()
    exported = [json.loads(line) for line in out.getvalue().strip().splitlines() if line]
    assert exported[-1]["type"] == "recording_exported"
