"""Integration tests for upload queue drain after pairing."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from meetrec.calls.client import build_call_title, compute_duration_sec
from meetrec.calls.pairing import apply_pairing_to_config
from meetrec.calls.queue import enqueue_upload, list_pending_jobs, pending_count, process_job
from meetrec.config import CONFIG_DIR


def _make_code(payload: dict) -> str:
    import base64

    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"v1.{raw}"


@pytest.fixture
def isolated_pending(monkeypatch, tmp_path):
    pending = tmp_path / "pending_uploads"
    failed = tmp_path / "failed_uploads"
    pending.mkdir()
    failed.mkdir()
    monkeypatch.setattr("meetrec.calls.queue.PENDING_DIR", str(pending))
    monkeypatch.setattr("meetrec.calls.queue.FAILED_DIR", str(failed))
    return pending


def test_enqueue_prefers_mixed_path_from_metadata(isolated_pending, tmp_path):
    mixed = tmp_path / "call_mixed.wav"
    mixed.write_bytes(b"RIFF" + b"\x00" * 128)

    job_id = enqueue_upload(
        audio_path=str(mixed),
        metadata={"mixed_file": str(mixed), "app": "Manual", "started_at": "2026-07-03T12:00:00+00:00"},
        project_id=None,
        api_base="https://calls.o2consult.ai",
    )
    jobs = list_pending_jobs()
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == job_id
    assert jobs[0]["audio_path"].endswith("_mixed.wav")


def test_process_job_success_removes_pending(isolated_pending, tmp_path):
    audio = tmp_path / "sample_mixed.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 128)
    enqueue_upload(
        audio_path=str(audio),
        metadata={"app": "Manual", "started_at": "2026-07-03T12:00:00+00:00"},
        project_id=None,
        api_base="https://calls.o2consult.ai",
    )
    assert pending_count() == 1

    def fake_upload(*args, **kwargs):
        return {"call_id": "11111111-1111-1111-1111-111111111111", "status": "uploaded"}

    result = process_job(
        list_pending_jobs()[0],
        token="device-token",
        upload_fn=fake_upload,
        build_title_fn=build_call_title,
        duration_fn=compute_duration_sec,
    )
    assert result == "success"
    assert pending_count() == 0


def test_apply_pairing_enables_worker_config():
    code = _make_code(
        {
            "api": "https://calls.o2consult.ai",
            "token": "tok-abc",
            "device_id": "11111111-1111-1111-1111-111111111111",
            "project_id": None,
        }
    )
    cfg = apply_pairing_to_config({}, code)
    assert cfg["calls_setup_completed"] is True
    assert cfg["calls_device_token"] == "tok-abc"
    assert cfg["calls_auto_upload"] is True
