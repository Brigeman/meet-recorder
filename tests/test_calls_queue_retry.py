"""Upload queue retry and error classification tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from meetrec.calls.client import CallsApiError
from meetrec.calls.queue import (
    classify_upload_error,
    enqueue_upload,
    list_pending_jobs,
    process_job,
)


@pytest.fixture
def pending_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("meetrec.calls.queue.PENDING_DIR", str(tmp_path / "pending"))
    monkeypatch.setattr("meetrec.calls.queue.FAILED_DIR", str(tmp_path / "failed"))
    monkeypatch.setattr("meetrec.calls.queue.ensure_pending_dir", lambda: None)
    return tmp_path


def test_classify_network_error():
    assert classify_upload_error(httpx.ConnectError("offline")) == "network"
    assert classify_upload_error(CallsApiError("server", status_code=503)) == "server_retry"
    assert classify_upload_error(CallsApiError("bad", status_code=400)) == "client_failed"


def test_process_job_network_error_retries_without_increment(pending_dir, tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF" + b"\0" * 64)
    enqueue_upload(
        audio_path=str(audio),
        metadata={"started_at": "2026-05-28T10:00:00"},
        project_id=None,
        api_base="https://calls.example.test",
    )
    job = list_pending_jobs()[0]

    def upload_fn(*args, **kwargs):
        raise httpx.ConnectError("vpn off")

    result = process_job(
        job,
        token="tok",
        upload_fn=upload_fn,
        build_title_fn=lambda meta, path: "title",
        duration_fn=lambda meta: 10,
    )
    assert result == "retry_network"
    job_after = list_pending_jobs()[0]
    assert job_after["attempts"] == 0


def test_process_job_client_error_moves_to_failed(pending_dir, tmp_path, monkeypatch):
    monkeypatch.setattr("meetrec.calls.queue.MAX_CLIENT_ATTEMPTS", 1)
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF" + b"\0" * 64)
    enqueue_upload(
        audio_path=str(audio),
        metadata={"started_at": "2026-05-28T10:00:00"},
        project_id=None,
        api_base="https://calls.example.test",
    )
    job = list_pending_jobs()[0]

    def upload_fn(*args, **kwargs):
        raise CallsApiError("bad request", status_code=400)

    result = process_job(
        job,
        token="tok",
        upload_fn=upload_fn,
        build_title_fn=lambda meta, path: "title",
        duration_fn=lambda meta: 10,
    )
    assert result == "failed"
    assert list_pending_jobs() == []
    assert (pending_dir / "failed").exists()


def test_process_job_uses_created_at_when_started_at_missing(pending_dir, tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF" + b"\0" * 64)
    enqueue_upload(
        audio_path=str(audio),
        metadata={"app": "Teams"},
        project_id=None,
        api_base="https://calls.example.test",
    )
    job = list_pending_jobs()[0]
    upload_fn = MagicMock(return_value={"call_id": "c1"})
    result = process_job(
        job,
        token="tok",
        upload_fn=upload_fn,
        build_title_fn=lambda meta, path: "title",
        duration_fn=lambda meta: None,
    )
    assert result == "success"
    assert upload_fn.call_args.kwargs["started_at"] == job["created_at"]
