"""HTTP client for Calls device API."""

from __future__ import annotations

import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


class CallsApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _api_url(api_base: str, path: str) -> str:
    base = api_base.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def build_call_title(metadata: dict[str, Any], audio_path: str) -> str:
    app = str(metadata.get("app") or "Meeting").strip() or "Meeting"
    started = metadata.get("started_at")
    if started:
        try:
            dt = datetime.fromisoformat(str(started))
            stamp = dt.strftime("%d.%m.%Y %H:%M")
            return f"{app} — {stamp}"
        except ValueError:
            pass
    return f"{app} — {Path(audio_path).stem}"


def compute_duration_sec(metadata: dict[str, Any]) -> int | None:
    started = metadata.get("started_at")
    ended = metadata.get("ended_at")
    if not started or not ended:
        return None
    try:
        start_dt = datetime.fromisoformat(str(started))
        end_dt = datetime.fromisoformat(str(ended))
        delta = int((end_dt - start_dt).total_seconds())
        return max(delta, 0)
    except ValueError:
        return None


def heartbeat(api_base: str, token: str) -> None:
    url = _api_url(api_base, "/api/devices/heartbeat/")
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.post(url, headers=_auth_headers(token), json={})
    if response.status_code >= 400:
        raise CallsApiError(
            f"Heartbeat failed (HTTP {response.status_code})",
            status_code=response.status_code,
        )


def upload_call(
    api_base: str,
    token: str,
    *,
    title: str,
    started_at: str,
    audio_path: str,
    project_id: str | None = None,
    duration_sec: int | None = None,
) -> dict[str, Any]:
    path = Path(audio_path)
    if not path.is_file():
        raise CallsApiError(f"Audio file not found: {audio_path}")
    size = path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        raise CallsApiError(f"Audio file too large ({size} bytes)")

    url = _api_url(api_base, "/api/calls/upload/")
    data: dict[str, str] = {
        "title": title,
        "started_at": started_at,
    }
    if project_id:
        data["project_id"] = project_id
    if duration_sec is not None:
        data["duration_sec"] = str(duration_sec)

    mime = _guess_mime(str(path))
    with path.open("rb") as audio_file:
        files = {"audio": (path.name, audio_file, mime)}
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.post(url, headers=_auth_headers(token), data=data, files=files)

    if response.status_code >= 400:
        detail = response.text[:300]
        log.warning("upload_failed status=%s body=%s", response.status_code, detail)
        raise CallsApiError(
            f"Upload failed (HTTP {response.status_code})",
            status_code=response.status_code,
        )

    body = response.json()
    log.info("upload_ok call_id=%s", body.get("call_id"))
    return body
