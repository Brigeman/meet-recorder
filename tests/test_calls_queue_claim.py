"""Upload queue concurrency tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from winrec.calls.queue import enqueue_upload, list_pending_jobs, process_job


def test_process_job_claim_prevents_double_upload(tmp_path, monkeypatch):
    monkeypatch.setattr("winrec.calls.queue.PENDING_DIR", str(tmp_path / "pending"))
    monkeypatch.setattr("winrec.calls.queue.ensure_pending_dir", lambda: None)

    audio_path = tmp_path / "call.wav"
    audio_path.write_bytes(b"RIFF")

    job_id = enqueue_upload(
        audio_path=str(audio_path),
        metadata={"started_at": "2026-06-24T12:00:00"},
        project_id=None,
        api_base="https://example.test",
    )

    upload_fn = MagicMock(return_value={"call_id": "abc"})
    jobs = list_pending_jobs()
    assert len(jobs) == 1

    first = process_job(
        jobs[0],
        token="token",
        upload_fn=upload_fn,
        build_title_fn=lambda metadata, path: "Title",
        duration_fn=lambda metadata: 10,
    )
    second = process_job(
        jobs[0],
        token="token",
        upload_fn=upload_fn,
        build_title_fn=lambda metadata, path: "Title",
        duration_fn=lambda metadata: 10,
    )

    assert first == "success"
    assert second == "busy"
    upload_fn.assert_called_once()
