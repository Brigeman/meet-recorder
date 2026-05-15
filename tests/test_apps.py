from winrec.detector.apps import PROCESS_TO_APP, webview2_has_valid_ancestor
from winrec.detector.scoring import match_title_hint


def test_process_to_app_teams():
    assert PROCESS_TO_APP["ms-teams.exe"] == "Microsoft Teams"


def test_title_hint_zoom():
    assert match_title_hint("Zoom Meeting with John") == "Zoom"


def test_title_hint_meet():
    assert match_title_hint("Meet - abc-defg-hij") == "Google Meet"


def test_webview2_function_exists():
    assert callable(webview2_has_valid_ancestor)
