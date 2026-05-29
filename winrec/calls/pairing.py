"""Parse v1 desktop pairing codes from Calls Settings."""

from __future__ import annotations

import base64
import json
from typing import Any


class PairingError(ValueError):
    pass


def parse_pairing_code(code: str) -> dict[str, Any]:
    raw = (code or "").strip()
    if not raw.startswith("v1."):
        raise PairingError("Неподдерживаемый формат кода подключения")

    payload_b64 = raw[3:]
    pad = "=" * (-len(payload_b64) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload_b64 + pad)
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PairingError("Некорректный код подключения") from exc

    if not isinstance(payload, dict):
        raise PairingError("Некорректный код подключения")

    api = str(payload.get("api", "")).strip().rstrip("/")
    token = str(payload.get("token", "")).strip()
    device_id = str(payload.get("device_id", "")).strip()
    if not api or not token or not device_id:
        raise PairingError("В коде отсутствуют обязательные поля")

    project_id = payload.get("project_id")
    if project_id is not None:
        project_id = str(project_id).strip() or None

    return {
        "api": api,
        "token": token,
        "device_id": device_id,
        "project_id": project_id,
    }


def apply_pairing_to_config(config: dict, code: str) -> dict:
    payload = parse_pairing_code(code)
    updated = dict(config)
    updated["calls_api_base_url"] = payload["api"]
    updated["calls_device_token"] = payload["token"]
    updated["calls_device_id"] = payload["device_id"]
    updated["calls_default_project_id"] = payload.get("project_id")
    updated["calls_setup_completed"] = True
    updated["calls_auto_upload"] = True
    updated["calls_setup_skipped"] = False
    return updated
