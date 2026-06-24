import base64
import json

import pytest

from meetrec.calls.pairing import PairingError, apply_pairing_to_config, parse_pairing_code


def _make_code(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"v1.{raw}"


def test_parse_pairing_code_ok():
    payload = {
        "api": "https://calls.o2consult.ai",
        "token": "secret-token",
        "device_id": "11111111-1111-1111-1111-111111111111",
        "project_id": "22222222-2222-2222-2222-222222222222",
    }
    parsed = parse_pairing_code(_make_code(payload))
    assert parsed["api"] == "https://calls.o2consult.ai"
    assert parsed["token"] == "secret-token"
    assert parsed["device_id"] == payload["device_id"]
    assert parsed["project_id"] == payload["project_id"]


def test_parse_pairing_code_rejects_bad_prefix():
    with pytest.raises(PairingError):
        parse_pairing_code("v2.abc")


def test_apply_pairing_to_config():
    code = _make_code(
        {
            "api": "https://calls.o2consult.ai/",
            "token": "tok",
            "device_id": "d1",
            "project_id": None,
        }
    )
    cfg = apply_pairing_to_config({}, code)
    assert cfg["calls_setup_completed"] is True
    assert cfg["calls_device_token"] == "tok"
    assert cfg["calls_api_base_url"] == "https://calls.o2consult.ai"
    assert cfg["calls_default_project_id"] is None
