"""Project picker auto-skip when default project is set or on macOS."""

from __future__ import annotations

import sys

import pytest


class _StubApp:
    _pending_record = {"app": "Manual"}

    def __init__(self, cfg: dict):
        self._cfg = cfg
        self._session_project_id = None


def _load_app_module():
    """Skip on headless Linux CI where pystray/Xlib cannot open a display."""
    try:
        from meetrec.gui import app as app_mod
    except Exception as exc:  # pragma: no cover - platform/display dependent
        pytest.skip(f"GUI app import unavailable: {exc}")
    return app_mod


def _bind_show_project_picker(stub: _StubApp):
    app_mod = _load_app_module()
    return app_mod.WinRecApp._show_project_picker.__get__(stub, app_mod.WinRecApp)


def test_skips_dialog_when_default_project_configured(monkeypatch):
    app_mod = _load_app_module()

    opened: list[bool] = []
    monkeypatch.setattr(
        app_mod,
        "ProjectPickerDialog",
        lambda *args, **kwargs: opened.append(True),
    )

    stub = _StubApp(
        {
            "calls_setup_completed": True,
            "calls_device_token": "device-token",
            "calls_default_project_id": "proj-default",
        }
    )
    confirmed: list[str | None] = []
    _bind_show_project_picker(stub)(confirmed.append)

    assert confirmed == ["proj-default"]
    assert stub._session_project_id == "proj-default"
    assert opened == []


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS menu-bar UI path")
def test_skips_dialog_on_macos_even_without_default(monkeypatch):
    app_mod = _load_app_module()

    opened: list[bool] = []
    monkeypatch.setattr(
        app_mod,
        "ProjectPickerDialog",
        lambda *args, **kwargs: opened.append(True),
    )

    stub = _StubApp(
        {
            "calls_setup_completed": True,
            "calls_device_token": "device-token",
            "calls_default_project_id": None,
        }
    )
    confirmed: list[str | None] = []
    _bind_show_project_picker(stub)(confirmed.append)

    assert confirmed == [None]
    assert stub._session_project_id is None
    assert opened == []


def test_shows_dialog_on_windows_when_no_default(monkeypatch):
    if sys.platform == "darwin":
        pytest.skip("Windows-only CTk picker path")

    app_mod = _load_app_module()

    opened: list[bool] = []
    monkeypatch.setattr(
        app_mod,
        "ProjectPickerDialog",
        lambda *args, **kwargs: opened.append(True),
    )

    stub = _StubApp(
        {
            "calls_setup_completed": True,
            "calls_device_token": "device-token",
            "calls_default_project_id": None,
        }
    )
    _bind_show_project_picker(stub)(lambda _pid: None)

    assert opened == [True]
