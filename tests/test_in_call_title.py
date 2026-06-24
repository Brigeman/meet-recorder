from meetrec.detector.apps import match_in_call_title


def test_teams_timer_title_detected():
    app, in_call = match_in_call_title("00:12:34 | Microsoft Teams")
    assert in_call
    assert app == "Microsoft Teams"


def test_zoom_meeting_detected():
    app, in_call = match_in_call_title("Zoom Meeting - Project Sync")
    assert in_call
    assert app == "Zoom"


def test_plain_teams_window_not_in_call():
    app, in_call = match_in_call_title("Microsoft Teams")
    assert not in_call
    assert app is None
