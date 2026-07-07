import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS app mapping")

from meetrec.platform.macos.apps import (
    _is_auxiliary_process,
    _match_exe_path,
    _match_process_name,
    resolve_bundle_id,
    resolve_localized_name,
)


def test_resolve_bundle_id_teams2():
    assert resolve_bundle_id("com.microsoft.teams2") == "Microsoft Teams"


def test_resolve_bundle_id_telegram():
    assert resolve_bundle_id("org.telegram.desktop") == "Telegram"
    assert resolve_bundle_id("ru.keepcoder.Telegram") == "Telegram"


def test_resolve_bundle_id_whatsapp():
    assert resolve_bundle_id("net.whatsapp.WhatsApp") == "WhatsApp"


def test_match_exe_path_telegram():
    assert (
        _match_exe_path("/Applications/Telegram.app/Contents/MacOS/Telegram")
        == "Telegram"
    )


def test_match_exe_path_whatsapp():
    assert (
        _match_exe_path("/Applications/WhatsApp.app/Contents/MacOS/WhatsApp")
        == "WhatsApp"
    )


def test_match_process_name_telegram_helper():
    assert _match_process_name("Telegram Helper") == "Telegram"


def test_resolve_bundle_id_rejects_updater():
    assert resolve_bundle_id("us.zoom.updater") is None


def test_match_process_name_msteams():
    assert _match_process_name("MSTeams") == "Microsoft Teams"


def test_match_process_name_teams2_truncated():
    assert _match_process_name("com.microsoft.teams2") == "Microsoft Teams"


def test_match_exe_path_teams_main():
    assert (
        _match_exe_path(
            "/Applications/Microsoft Teams.app/Contents/MacOS/MSTeams"
        )
        == "Microsoft Teams"
    )


def test_match_exe_path_rejects_launch_agent():
    assert (
        _match_exe_path(
            "/Applications/Microsoft Teams.app/Contents/Library/LaunchAgents/com.microsoft.teams2.agent"
        )
        is None
    )


def test_is_auxiliary_process_agent():
    assert _is_auxiliary_process(
        bundle_id="com.microsoft.teams2.agent",
        exe="/Applications/Microsoft Teams.app/Contents/Library/LaunchAgents/com.microsoft.teams2.agent",
    )


def test_resolve_localized_name_teams():
    assert resolve_localized_name("Microsoft Teams") == "Microsoft Teams"


def test_resolve_localized_name_zoom_workplace():
    assert resolve_localized_name("zoom.us") == "Zoom"
