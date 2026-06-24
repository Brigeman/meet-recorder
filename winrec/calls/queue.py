"""Persistent upload queue for finished recordings."""

from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from winrec.config import CONFIG_DIR

log = logging.getLogger(__name__)

PENDING_DIR = os.path.join(CONFIG_DIR, "pending_uploads")
MAX_ATTEMPTS = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _job_dir(job_id: str) -> Path:
    return Path(PENDING_DIR) / job_id


def ensure_pending_dir() -> None:
    os.makedirs(PENDING_DIR, exist_ok=True)


def enqueue_upload(
    *,
    audio_path: str,
    metadata: dict[str, Any],
    project_id: str | None,
    api_base: str,
) -> str:
    ensure_pending_dir()
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(audio_path)

    job_id = str(uuid.uuid4())
    job_path = _job_dir(job_id)
    job_path.mkdir(parents=True, exist_ok=False)

    stored_audio = job_path / Path(audio_path).name
    shutil.copy2(audio_path, stored_audio)

    job = {
        "job_id": job_id,
        "audio_path": str(stored_audio),
        "metadata": dict(metadata),
        "project_id": project_id,
        "api_base": api_base.rstrip("/"),
        "attempts": 0,
        "created_at": _now_iso(),
        "last_error": None,
    }
    with open(job_path / "job.json", "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2, ensure_ascii=False)

    log.info("upload_enqueued job_id=%s audio=%s", job_id, stored_audio.name)
    return job_id


def list_pending_jobs() -> list[dict[str, Any]]:
    ensure_pending_dir()
    jobs: list[dict[str, Any]] = []
    for entry in sorted(Path(PENDING_DIR).iterdir()):
        if not entry.is_dir():
            continue
        job_file = entry / "job.json"
        if not job_file.is_file():
            continue
        try:
            with open(job_file, encoding="utf-8") as f:
                jobs.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            log.warning("invalid_job_file path=%s", job_file)
    jobs.sort(key=lambda item: item.get("created_at", ""))
    return jobs


def _write_job(job_path: Path, job: dict[str, Any]) -> None:
    with open(job_path / "job.json", "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2, ensure_ascii=False)


def _remove_job_dir(job_path: Path) -> None:
    shutil.rmtree(job_path, ignore_errors=True)


def process_job(
    job: dict[str, Any],
    *,
    token: str,
    upload_fn: Callable[..., dict[str, Any]],
    build_title_fn: Callable[[dict[str, Any], str], str],
    duration_fn: Callable[[dict[str, Any]], int | None],
) -> str:
    """Returns: success | retry | abandoned."""
    job_id = job["job_id"]
    job_path = _job_dir(job_id)
    metadata = job.get("metadata") or {}
    audio_path = job.get("audio_path") or ""
    started_at = metadata.get("started_at")
    if not started_at:
        log.error("upload_job_missing_started_at job_id=%s", job_id)
        _remove_job_dir(job_path)
        return "abandoned"

    try:
        upload_fn(
            job["api_base"],
            token,
            title=build_title_fn(metadata, audio_path),
            started_at=str(started_at),
            audio_path=audio_path,
            project_id=job.get("project_id"),
            duration_sec=duration_fn(metadata),
            ended_at=str(metadata.get("ended_at")) if metadata.get("ended_at") else None,
            app=str(metadata.get("app")) if metadata.get("app") else None,
            meeting_hint=str(metadata.get("meeting_hint")) if metadata.get("meeting_hint") else None,
        )
        _remove_job_dir(job_path)
        return "success"
    except Exception as exc:
        attempts = int(job.get("attempts", 0)) + 1
        job["attempts"] = attempts
        job["last_error"] = str(exc)
        _write_job(job_path, job)
        log.warning("upload_job_failed job_id=%s attempts=%s error=%s", job_id, attempts, exc)
        if attempts >= MAX_ATTEMPTS:
            log.error("upload_job_abandoned job_id=%s", job_id)
            _remove_job_dir(job_path)
            return "abandoned"
        return "retry"
