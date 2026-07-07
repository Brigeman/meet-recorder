"""Headless wiring tests for the recording panel.

Windows: FloatingPanel (Tk) button / escape wiring.
macOS: NativePanel facade and ObjC PanelTarget → _post_to_ui callbacks.
"""

from __future__ import annotations

import sys

import pytest

ctk = pytest.importorskip("customtkinter")


@pytest.fixture()
def root():
    try:
        r = ctk.CTk()
    except Exception as exc:  # no display / Tk unavailable
        pytest.skip(f"Tk unavailable: {exc}")
    r.withdraw()
    try:
        yield r
    finally:
        try:
            r.destroy()
        except Exception:
            pass


def _make_floating_panel(root):
    from meetrec.gui.panel import FloatingPanel

    calls = {"stop": 0, "start": 0}
    panel = FloatingPanel(
        root,
        on_stop=lambda: calls.__setitem__("stop", calls["stop"] + 1),
        on_start=lambda: calls.__setitem__("start", calls["start"] + 1),
    )
    return panel, calls


def _make_native_panel(root):
    from meetrec.gui.native_panel_macos import NativePanel

    calls = {"stop": 0, "start": 0}
    panel = NativePanel(
        root,
        on_stop=lambda: calls.__setitem__("stop", calls["stop"] + 1),
        on_start=lambda: calls.__setitem__("start", calls["start"] + 1),
    )
    return panel, calls


def _make_panel(root):
    if sys.platform == "darwin":
        return _make_native_panel(root)
    return _make_floating_panel(root)


# --- Shared facade tests (factory-selected panel) ---


def test_panel_factory_selects_native_on_darwin(root):
    from meetrec.gui.panel_factory import create_recording_panel

    panel = create_recording_panel(root, lambda: None, lambda: None)
    if sys.platform == "darwin":
        from meetrec.gui.native_panel_macos import NativePanel

        assert isinstance(panel, NativePanel)
    else:
        from meetrec.gui.panel import FloatingPanel

        assert isinstance(panel, FloatingPanel)


def test_on_action_invokes_stop_when_recording(root):
    panel, calls = _make_panel(root)
    panel._recording = True
    panel._on_action()
    assert calls == {"stop": 1, "start": 0}


def test_on_action_invokes_start_when_idle(root):
    panel, calls = _make_panel(root)
    panel._recording = False
    panel._on_action()
    assert calls == {"stop": 0, "start": 1}


def test_on_action_emits_stop_clicked_log(root, monkeypatch):
    from meetrec.gui import native_panel_macos as native_mod
    from meetrec.gui import panel as panel_mod

    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        native_mod if sys.platform == "darwin" else panel_mod,
        "log_event",
        lambda event, **f: events.append((event, f)),
    )

    panel, calls = _make_panel(root)
    panel._recording = True
    panel._on_action()
    assert calls["stop"] == 1
    if sys.platform == "darwin":
        assert ("stop_clicked", {"source": "native_panel"}) in events
    else:
        assert ("stop_clicked", {"source": "panel_button"}) in events


def test_native_panel_has_floating_panel_surface(root):
    if sys.platform != "darwin":
        pytest.skip("macOS-only interface check")
    panel, _ = _make_native_panel(root)
    for name in (
        "show_recording",
        "show_idle_ready",
        "show_stopping",
        "hide_panel",
        "set_peak",
        "is_visible",
        "_recording",
        "_on_action",
    ):
        assert hasattr(panel, name)


def test_on_action_ignored_while_stopping(root):
    panel, calls = _make_panel(root)
    panel._recording = True
    panel._stopping = True
    panel._on_action()
    assert calls == {"stop": 0, "start": 0}


def test_native_panel_target_posts_to_ui(root):
    if sys.platform != "darwin":
        pytest.skip("macOS-only ObjC target")
    from meetrec.gui.native_panel_macos import _PanelTarget

    posted: list = []
    root._post_to_ui = lambda fn: posted.append(fn)

    panel, calls = _make_native_panel(root)
    panel._recording = True
    target = _PanelTarget.alloc().initWithTkApp_actionCallback_(root, panel._on_action)
    target.panelAction_(None)

    assert len(posted) == 1
    posted[0]()
    assert calls == {"stop": 1, "start": 0}


def test_native_panel_target_switches_start_when_idle(root):
    if sys.platform != "darwin":
        pytest.skip("macOS-only ObjC target")
    from meetrec.gui.native_panel_macos import _PanelTarget

    posted: list = []
    root._post_to_ui = lambda fn: posted.append(fn)

    panel, calls = _make_native_panel(root)
    panel._recording = False
    target = _PanelTarget.alloc().initWithTkApp_actionCallback_(root, panel._on_action)
    target.panelAction_(None)
    posted[0]()
    assert calls == {"stop": 0, "start": 1}


def test_native_panel_show_hide_visibility(root):
    if sys.platform != "darwin":
        pytest.skip("macOS-only panel lifecycle")
    panel, _ = _make_native_panel(root)
    assert panel.is_visible is False
    panel.show_recording()
    assert panel.is_visible is True
    assert panel._recording is True
    panel.hide_panel()
    assert panel.is_visible is False


# --- Windows FloatingPanel specifics ---


def test_floating_action_button_command_is_wired(root):
    if sys.platform == "darwin":
        pytest.skip("Windows-only FloatingPanel")
    panel, _ = _make_floating_panel(root)
    assert panel._action_btn.cget("command") == panel._action


def test_floating_button_invoke_calls_action_exactly_once(root):
    if sys.platform == "darwin":
        pytest.skip("Windows-only FloatingPanel")
    panel, calls = _make_floating_panel(root)
    panel._recording = True
    panel.invoke_action_button()
    assert calls == {"stop": 1, "start": 0}


def test_floating_escape_stops_only_while_recording(root):
    if sys.platform == "darwin":
        pytest.skip("Windows-only FloatingPanel")
    panel, calls = _make_floating_panel(root)
    panel._recording = False
    panel._on_escape()
    assert calls["stop"] == 0
    panel._recording = True
    panel._on_escape()
    assert calls["stop"] == 1


def test_floating_escape_emits_stop_clicked_log(root, monkeypatch):
    if sys.platform == "darwin":
        pytest.skip("Windows-only FloatingPanel")
    from meetrec.gui import panel as panel_mod

    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(panel_mod, "log_event", lambda event, **f: events.append((event, f)))

    panel, _ = _make_floating_panel(root)
    panel._recording = True
    panel._on_escape()
    assert ("stop_clicked", {"source": "escape"}) in events


def test_floating_button_release_handler_is_bound_on_inner_canvas(root):
    if sys.platform == "darwin":
        pytest.skip("Windows-only FloatingPanel")
    panel, _ = _make_floating_panel(root)
    bound = panel._action_btn._canvas.bind()
    assert "<ButtonRelease-1>" in bound


def test_floating_button_release_handler_triggers_stop(root):
    if sys.platform == "darwin":
        pytest.skip("Windows-only FloatingPanel")
    panel, calls = _make_floating_panel(root)
    panel._recording = True
    panel._last_action_ts = 0.0
    panel._on_button_click()
    assert calls == {"stop": 1, "start": 0}


def test_floating_button_release_handler_debounced_after_command(root):
    if sys.platform == "darwin":
        pytest.skip("Windows-only FloatingPanel")
    panel, calls = _make_floating_panel(root)
    panel._recording = True
    panel._action()
    assert calls["stop"] == 1
    panel._on_button_click()
    assert calls["stop"] == 1


class _FakeEvent:
    def __init__(self, x_root, y_root):
        self.x_root = x_root
        self.y_root = y_root


def test_floating_drag_updates_window_geometry(root):
    if sys.platform == "darwin":
        pytest.skip("Windows-only FloatingPanel drag")
    panel, _ = _make_floating_panel(root)
    panel.update_idletasks()
    panel.geometry("+100+100")
    panel.update_idletasks()
    panel._start_drag(_FakeEvent(150, 150))
    assert isinstance(panel._drag_x, int)
    assert isinstance(panel._drag_y, int)
    panel._on_drag(_FakeEvent(190, 180))
    panel.update_idletasks()
    assert panel.winfo_x() == 100 + 40
    assert panel.winfo_y() == 100 + 30
