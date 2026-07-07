from meetrec.detector.titles import match_in_call_title, match_title_hint


def test_title_hint_telemost():
    assert match_title_hint("Телемост — Встреча") == "Yandex Telemost"


def test_title_hint_telemost_en():
    assert match_title_hint("Telemost call") == "Yandex Telemost"


def test_title_hint_webex():
    assert match_title_hint("Webex Meeting - standup") == "Webex"


def test_in_call_telemost():
    app, in_call = match_in_call_title("Телемост — standup")
    assert in_call and app == "Yandex Telemost"


def test_in_call_telegram():
    app, in_call = match_in_call_title("Voice call - Telegram")
    assert in_call and app == "Telegram"


def test_in_call_whatsapp():
    app, in_call = match_in_call_title("Video call — WhatsApp")
    assert in_call and app == "WhatsApp"


def test_loose_meet_word_does_not_match():
    assert match_title_hint("Nice to meet you") is None


def test_meet_google_url_matches():
    assert match_title_hint("meet.google.com/abc-defg-hij") == "Google Meet"


def test_in_call_google_meet_tab():
    app, in_call = match_in_call_title("Google Meet - abc-defg-hij")
    assert in_call and app == "Google Meet"
