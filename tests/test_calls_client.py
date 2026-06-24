from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from meetrec.calls.client import (
    CallsApiError,
    build_call_title,
    compute_duration_sec,
    heartbeat,
    upload_call,
)


def test_build_call_title_from_metadata():
    title = build_call_title({"app": "Teams", "started_at": "2026-05-28T15:30:00"}, "x.wav")
    assert title.startswith("Teams — ")


def test_compute_duration_sec():
    meta = {
        "started_at": "2026-05-28T10:00:00",
        "ended_at": "2026-05-28T10:01:30",
    }
    assert compute_duration_sec(meta) == 90


def test_heartbeat_ok():
    response = MagicMock(status_code=200)
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = response
    with patch("meetrec.calls.client.httpx.Client", return_value=client):
        heartbeat("https://calls.o2consult.ai", "token")
    client.post.assert_called_once()


def test_upload_call_success(tmp_path):
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"RIFF....")

    response = MagicMock(status_code=201)
    response.json.return_value = {"call_id": "abc", "status": "uploaded"}

    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = response

    with patch("meetrec.calls.client.httpx.Client", return_value=client):
        body = upload_call(
            "https://calls.o2consult.ai",
            "token",
            title="Test",
            started_at="2026-05-28T10:00:00",
            audio_path=str(audio),
            project_id="proj",
            duration_sec=30,
        )
    assert body["call_id"] == "abc"


def test_upload_call_http_error(tmp_path):
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"RIFF....")

    response = MagicMock(status_code=500, text="boom")
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = response

    with patch("meetrec.calls.client.httpx.Client", return_value=client):
        with pytest.raises(CallsApiError):
            upload_call(
                "https://calls.o2consult.ai",
                "token",
                title="Test",
                started_at="2026-05-28T10:00:00",
                audio_path=str(audio),
            )
