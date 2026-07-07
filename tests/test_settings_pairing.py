"""Settings pairing UI helpers."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from meetrec.calls.pairing import PairingError, apply_pairing_to_config
from meetrec.gui.settings import SettingsWindow


def test_settings_window_accepts_pairing_callback():
    assert "on_pairing_complete" in SettingsWindow.__init__.__code__.co_varnames


def test_reset_pairing_on_darwin_skips_setup_wizard():
    from meetrec.gui.app import WinRecApp

    app = MagicMock()
    app._cfg = {
        "calls_setup_completed": True,
        "calls_device_token": "tok",
        "calls_device_id": "d1",
        "calls_default_project_id": "p1",
        "calls_setup_skipped": False,
    }

    with patch("meetrec.gui.app.sys.platform", "darwin"), patch(
        "meetrec.gui.app.save_config"
    ) as save_cfg:
        WinRecApp._on_reset_pairing(app, reopen_settings=False)

    save_cfg.assert_called_once()
    assert app._cfg["calls_device_token"] == ""
    assert app._cfg["calls_setup_completed"] is False
    app._maybe_show_setup_wizard.assert_not_called()


def test_reset_pairing_on_windows_opens_setup_wizard():
    from meetrec.gui.app import WinRecApp

    app = MagicMock()
    app._cfg = {
        "calls_setup_completed": True,
        "calls_device_token": "tok",
        "calls_device_id": "d1",
        "calls_default_project_id": None,
        "calls_setup_skipped": False,
    }

    with patch("meetrec.gui.app.sys.platform", "win32"), patch(
        "meetrec.gui.app.save_config"
    ):
        WinRecApp._on_reset_pairing(app)

    app._maybe_show_setup_wizard.assert_called_once_with(force=True)


def test_connect_calls_applies_pairing(monkeypatch):
    saved = {}

    def fake_save(cfg):
        saved["cfg"] = dict(cfg)

    monkeypatch.setattr("meetrec.gui.settings.save_config", fake_save)

    window = SettingsWindow.__new__(SettingsWindow)
    window._cfg = {}
    window._pairing_code_var = MagicMock()
    window._pairing_code_var.get.return_value = "bad"
    window._pairing_error_label = MagicMock()
    window._on_save = MagicMock()
    window._on_pairing_complete = MagicMock()
    window.destroy = MagicMock()

    with patch(
        "meetrec.gui.settings.apply_pairing_to_config",
        side_effect=PairingError("bad code"),
    ):
        window._connect_calls()
    window._pairing_error_label.configure.assert_called_with(text="bad code")
    window.destroy.assert_not_called()
