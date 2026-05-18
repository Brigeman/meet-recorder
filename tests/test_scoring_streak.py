from winrec.detector.scoring import SignalSnapshot, compute_matched, compute_score


def test_meeting_audio_not_counted_without_streak_or_in_call():
    snap = SignalSnapshot(
        meeting_capture_active=True,
        meeting_render_active=True,
        meeting_network_active=True,
        apps_running={"Microsoft Teams"},
        foreground_app="Microsoft Teams",
        title_hint_app="Microsoft Teams",
    )
    score = compute_score(
        snap,
        cap_streak=2.0,
        ren_streak=2.0,
        audio_streak_threshold=8.0,
    )
    assert score == 60
    matched = compute_matched(
        snap,
        cap_streak=2.0,
        ren_streak=2.0,
        audio_streak_threshold=8.0,
    )
    assert "meeting_app_capture_active" not in matched
    assert "meeting_app_render_active" not in matched


def test_meeting_audio_counted_after_streak_threshold():
    snap = SignalSnapshot(
        meeting_capture_active=True,
        meeting_render_active=True,
        meeting_network_active=True,
        apps_running={"Microsoft Teams"},
        foreground_app="Microsoft Teams",
        title_hint_app="Microsoft Teams",
    )
    score = compute_score(
        snap,
        cap_streak=8.1,
        ren_streak=8.1,
        audio_streak_threshold=8.0,
    )
    assert score == 110


def test_in_call_title_bypasses_streak_gate():
    snap = SignalSnapshot(
        meeting_capture_active=True,
        meeting_render_active=True,
        meeting_network_active=True,
        in_call_title_app="Microsoft Teams",
        apps_running={"Microsoft Teams"},
        foreground_app="Microsoft Teams",
    )
    score = compute_score(
        snap,
        cap_streak=0.1,
        ren_streak=0.1,
        audio_streak_threshold=8.0,
    )
    assert score == 125
