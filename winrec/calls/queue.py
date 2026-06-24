"""Persistent upload queue for finished recordings."""

from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

import httpx

from winrec.calls.client import CallsApiError
from winrec.config import CONFIG_DIR

log = logging.getLogger(__name__)

PENDING_DIR = os.path.join(CONFIG_DIR, "pending_uploads")
FAILED_DIR = os.path.join(CONFIG_DIR, "failed_uploads")
MAX_CLIENT_ATTEMPTS = 3
MIN_AUDIO_BYTES = 44

UploadErrorKind = Literal["network", "server_retry", "client_failed"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _job_dir(job_id: str) -> Path:
    return Path(PENDING_DIR) / job_id


def ensure_pending_dir() -> None:
    os.makedirs(PENDING_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)


def classify_upload_error(exc: BaseException) -> UploadErrorKind:
    if isinstance(exc, CallsApiError):
        if exc.status_code is not None and exc.status_code >= 500:
            return "server_retry"
        return "client_failed"
    if isinstance(exc, httpx.HTTPError):
        return "network"
    return "client_failed"


def pending_count() -> int:
    return len(list_pending_jobs())


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
    size = os.path.getsize(audio_path)
    if size < MIN_AUDIO_BYTES:
        raise ValueError(f"audio file too small: {size} bytes")

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


def _move_job_to_failed(job_path: Path, job: dict[str, Any], reason: str) -> None:
    ensure_pending_dir()
    dest = Path(FAILED_DIR) / job_path.name
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    job["failed_at"] = _now_iso()
    job["fail_reason"] = reason
    _write_job(job_path, job)
    shutil.move(str(job_path), str(dest))
    log.error("upload_job_failed_permanent job_id=%s reason=%s", job.get("job_id"), reason)


def _ensure_started_at(metadata: dict[str, Any], job: dict[str, Any]) -> str:
    started = metadata.get("started_at")
    if started:
        return str(started)
    created = job.get("created_at")
    if created:
        return str(created)
    return _now_iso()


def _try_claim_job(job_path: Path) -> bool:
    lock_path = job_path / "job.lock"
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except OSError:
        return False


def _release_job_lock(job_path: Path) -> None:
    lock_path = job_path / "job.lock"
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass


def process_job(
    job: dict[str, Any],
    *,
    token: str,
    upload_fn: Callable[..., dict[str, Any]],
    build_title_fn: Callable[[dict[str, Any], str], str],
    duration_fn: Callable[[dict[str, Any]], int | None],
) -> str:
    """Returns: success | retry | retry_network | failed | busy."""
    job_id = job["job_id"]
    job_path = _job_dir(job_id)
    if not _try_claim_job(job_path):
        return "busy"
    metadata = dict(job.get("metadata") or {})
    audio_path = job.get("audio_path") or ""
    started_at = _ensure_started_at(metadata, job)
    metadata["started_at"] = started_at

    try:
        upload_fn(
            job["api_base"],
            token,
            title=build_title_fn(metadata, audio_path),
            started_at=started_at,
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
        kind = classify_upload_error(exc)
        job["last_error"] = str(exc)
        job["last_error_kind"] = kind
        log.warning(
            "upload_job_failed job_id=%s kind=%s error=%s",
            job_id,
            kind,
            exc,
        )
        if kind in ("network", "server_retry"):
            _write_job(job_path, job)
            return "retry_network"
        attempts = int(job.get("attempts", 0)) + 1
        job["attempts"] = attempts
        _write_job(job_path, job)
        if attempts >= MAX_CLIENT_ATTEMPTS:
            _move_job_to_failed(job_path, job, str(exc))
            return "failed"
        return "retry"
    finally:
        _release_job_lock(job_path)
