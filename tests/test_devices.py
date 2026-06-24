"""Tests for WASAPI device selection helpers."""

import sys
from unittest.mock import MagicMock

import pytest

if "pyaudiowpatch" not in sys.modules:
    _fake_pyaudio = MagicMock()
    _fake_pyaudio.paWASAPI = 13
    sys.modules["pyaudiowpatch"] = _fake_pyaudio

from winrec.recorder import devices
def _mock_pyaudio(
    *,
    devices_list: list[dict],
    default_output: int = 0,
    default_input: int = 1,
    loopback_via_api: dict | None = None,
    loopback_api_error: Exception | None = None,
):
    p = MagicMock()
    p.get_device_count.return_value = len(devices_list)
    p.get_device_info_by_index.side_effect = lambda i: devices_list[i]
    p.get_host_api_info_by_type.return_value = {
        "defaultOutputDevice": default_output,
        "defaultInputDevice": default_input,
    }
    if loopback_api_error:
        p.get_default_wasapi_loopback.side_effect = loopback_api_error
    elif loopback_via_api is not None:
        p.get_default_wasapi_loopback.return_value = loopback_via_api
    else:
        del p.get_default_wasapi_loopback
    return p


def test_find_loopback_prefers_get_default_wasapi_loopback():
    api_dev = {"name": "Headphones (loopback)", "index": 5, "isLoopbackDevice": True}
    p = _mock_pyaudio(
        devices_list=[{"name": "Speakers", "index": 0}],
        loopback_via_api=api_dev,
    )
    assert devices.find_loopback_device(p) == api_dev


def test_find_loopback_falls_back_to_name_match():
    devices_list = [
        {"name": "Speakers (Realtek)", "index": 0, "maxInputChannels": 0},
        {"name": "[Loopback] Speakers (Realtek)", "index": 2, "isLoopbackDevice": True},
    ]
    p = _mock_pyaudio(devices_list=devices_list, default_output=0)
    dev = devices.find_loopback_device(p)
    assert dev["index"] == 2


def test_find_loopback_falls_back_to_any_loopback():
    devices_list = [
        {"name": "Other", "index": 0},
        {"name": "Generic Loopback", "index": 3, "isLoopbackDevice": True},
    ]
    p = _mock_pyaudio(devices_list=devices_list, default_output=0)
    dev = devices.find_loopback_device(p)
    assert dev["index"] == 3


def test_find_loopback_raises_when_none_available():
    p = _mock_pyaudio(devices_list=[{"name": "Speakers", "index": 0}])
    with pytest.raises(RuntimeError, match="No WASAPI loopback"):
        devices.find_loopback_device(p)


def test_find_mic_returns_default_input():
    mic = {"name": "Headset Mic", "index": 4, "maxInputChannels": 1}
    p = _mock_pyaudio(devices_list=[{}, mic], default_input=1)
    assert devices.find_mic_device(p) == mic


def test_find_mic_returns_none_when_no_default_input():
    p = _mock_pyaudio(devices_list=[], default_input=-1)
    assert devices.find_mic_device(p) is None


def test_default_output_key():
    p = _mock_pyaudio(
        devices_list=[{"name": "Speakers", "index": 0}],
        default_output=0,
    )
    assert devices.default_output_key(p) == (0, "Speakers")


def test_default_input_key_none_when_missing():
    p = _mock_pyaudio(devices_list=[], default_input=-1)
    assert devices.default_input_key(p) is None
