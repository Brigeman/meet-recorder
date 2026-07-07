import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows app mapping")

from meetrec.detector.titles import match_title_hint
from meetrec.platform.windows.apps import PROCESS_TO_APP, webview2_has_valid_ancestor


def test_process_to_app_teams():
    assert PROCESS_TO_APP["ms-teams.exe"] == "Microsoft Teams"


def test_title_hint_zoom():
    assert match_title_hint("Zoom Meeting with John") == "Zoom"


def test_title_hint_meet():
    assert match_title_hint("Google Meet - abc-defg-hij") == "Google Meet"
    assert match_title_hint("Meet - abc-defg-hij") is None


def test_webview2_function_exists():
    assert callable(webview2_has_valid_ancestor)
