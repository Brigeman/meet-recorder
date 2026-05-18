from winrec.gui.icons import load_logo_image, make_tray_icon


def test_load_logo_image_has_requested_size():
    img = load_logo_image(48)
    assert img.size == (48, 48)


def test_recording_tray_icon_differs_from_idle():
    idle = make_tray_icon("monitoring", 64)
    recording = make_tray_icon("recording", 64)
    assert idle.tobytes() != recording.tobytes()
