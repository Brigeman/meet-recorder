import json
import os
from unittest.mock import patch

import pytest

from winrec.calls import queue as upload_queue


@pytest.fixture
def pending_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_queue, "PENDING_DIR", str(tmp_path / "pending"))
    upload_queue.ensure_pending_dir()
    return upload_queue.PENDING_DIR


def test_enqueue_and_list_pending(pending_dir, tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF....")

    job_id = upload_queue.enqueue_upload(
        audio_path=str(audio),
        metadata={"started_at": "2026-05-28T10:00:00", "app": "Teams"},
        project_id="proj-1",
        api_base="https://calls.o2consult.ai",
    )
    assert job_id

    jobs = upload_queue.list_pending_jobs()
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == job_id
    assert jobs[0]["project_id"] == "proj-1"
    assert os.path.isfile(jobs[0]["audio_path"])


def test_process_job_success_removes_pending(pending_dir, tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF....")
    job_id = upload_queue.enqueue_upload(
        audio_path=str(audio),
        metadata={"started_at": "2026-05-28T10:00:00", "app": "Zoom"},
        project_id=None,
        api_base="https://calls.o2consult.ai",
    )
    job = upload_queue.list_pending_jobs()[0]

    def upload_fn(*args, **kwargs):
        return {"call_id": "c1", "status": "uploaded"}

    result = upload_queue.process_job(
        job,
        token="tok",
        upload_fn=upload_fn,
        build_title_fn=lambda meta, path: "title",
        duration_fn=lambda meta: 10,
    )
    assert result == "success"
    assert upload_queue.list_pending_jobs() == []


def test_process_job_retries_then_abandons(pending_dir, tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF....")
    upload_queue.enqueue_upload(
        audio_path=str(audio),
        metadata={"started_at": "2026-05-28T10:00:00", "app": "Zoom"},
        project_id=None,
        api_base="https://calls.o2consult.ai",
    )

    def upload_fn(*args, **kwargs):
        raise RuntimeError("network down")

    with patch.object(upload_queue, "MAX_ATTEMPTS", 2):
        job = upload_queue.list_pending_jobs()[0]
        assert upload_queue.process_job(job, token="tok", upload_fn=upload_fn, build_title_fn=lambda m, p: "t", duration_fn=lambda m: None) == "retry"
        job = upload_queue.list_pending_jobs()[0]
        assert upload_queue.process_job(job, token="tok", upload_fn=upload_fn, build_title_fn=lambda m, p: "t", duration_fn=lambda m: None) == "abandoned"
        assert upload_queue.list_pending_jobs() == []
