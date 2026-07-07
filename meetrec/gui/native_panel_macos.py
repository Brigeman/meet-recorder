"""Native macOS recording panel — NSPanel + NSButton (reliable clicks, no Tk mouse)."""

from __future__ import annotations

import logging
import time
from typing import Callable

import objc
from Foundation import NSObject

from meetrec.gui.theme import (
    ACCENT_REC,
    BTN_PRIMARY,
    BTN_STOP,
    GLASS_BG,
    GLASS_BORDER,
    PANEL_H,
    PANEL_W,
    STATE_COLORS,
    TEXT_PRIMARY,
)
from meetrec.logging_util import log_event

log = logging.getLogger(__name__)

# AppKit style / level constants (avoid importing obscure symbols).
_NS_BORDERLESS = 0
_NS_NONACTIVATING_PANEL = 1 << 7
_NS_STATUS_WINDOW_LEVEL = 25
_NS_CAN_JOIN_ALL_SPACES = 1 << 0
_NS_STATIONARY = 1 << 4
_NS_FULLSCREEN_AUXILIARY = 1 << 8
_NS_BEZEL_ROUNDED = 1
_NS_BEZEL_PUSH = 3
_NS_ON_STATE = 1


def _hex_to_nscolor(hex_color: str, alpha: float = 1.0):
    from AppKit import NSColor

    value = hex_color.lstrip("#")
    if len(value) != 6:
        return NSColor.whiteColor()
    r = int(value[0:2], 16) / 255.0
    g = int(value[2:4], 16) / 255.0
    b = int(value[4:6], 16) / 255.0
    return NSColor.colorWithRed_green_blue_alpha_(r, g, b, alpha)


class _PanelTarget(NSObject):
    """ObjC target for the native action button."""

    def initWithTkApp_actionCallback_(self, tk_app, action_callback):
        self = objc.super(_PanelTarget, self).init()
        if self is None:
            return None
        self._tk_app = tk_app
        self._on_action = action_callback
        return self

    def panelAction_(self, sender):  # noqa: N802
        log_event("native_panel_action_clicked")
        self._tk_app._post_to_ui(self._on_action)


class NativePanel:
    """AppKit recording capsule; same surface as FloatingPanel for app.py."""

    def __init__(
        self,
        tk_app,
        on_stop: Callable[[], None],
        on_start: Callable[[], None],
    ):
        self._tk_app = tk_app
        self._on_stop = on_stop
        self._on_start = on_start
        self._recording = False
        self._stopping = False
        self._visible = False
        self._start_ts: float | None = None
        self._timer_job = None
        self._panel = None
        self._timer_field = None
        self._action_btn = None
        self._rec_dot = None
        self._level_bar = None
        self._target = None
        self._build_panel()

    @property
    def is_visible(self) -> bool:
        return self._visible

    def _on_action(self) -> None:
        if self._stopping:
            return
        if self._recording:
            log_event("stop_clicked", source="native_panel")
            self._on_stop()
        else:
            log_event("start_clicked", source="native_panel")
            self._on_start()

    def _build_panel(self) -> None:
        from AppKit import (
            NSBackingStoreBuffered,
            NSButton,
            NSColor,
            NSFont,
            NSMakeRect,
            NSPanel,
            NSProgressIndicator,
            NSTextField,
            NSView,
            NSWindowStyleMaskBorderless,
            NSWindowStyleMaskNonactivatingPanel,
        )
        from Foundation import NSMakeSize

        width, height = PANEL_W, PANEL_H
        style = int(NSWindowStyleMaskBorderless) | int(NSWindowStyleMaskNonactivatingPanel)
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, width, height),
            style,
            NSBackingStoreBuffered,
            False,
        )
        self._panel.setLevel_(_NS_STATUS_WINDOW_LEVEL)
        self._panel.setCollectionBehavior_(
            _NS_CAN_JOIN_ALL_SPACES | _NS_STATIONARY | _NS_FULLSCREEN_AUXILIARY
        )
        self._panel.setHidesOnDeactivate_(False)
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(NSColor.clearColor())
        self._panel.setHasShadow_(True)
        self._panel.setFloatingPanel_(True)
        self._panel.setBecomesKeyOnlyIfNeeded_(True)
        self._panel.setMovableByWindowBackground_(True)

        content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        content.setWantsLayer_(True)
        layer = content.layer()
        if layer is not None:
            layer.setBackgroundColor_(_hex_to_nscolor(GLASS_BG).CGColor())
            layer.setCornerRadius_(14.0)
            layer.setBorderWidth_(1.0)
            layer.setBorderColor_(_hex_to_nscolor(GLASS_BORDER).CGColor())
        self._panel.setContentView_(content)

        # Recording dot
        dot_size = 10.0
        self._rec_dot = NSView.alloc().initWithFrame_(
            NSMakeRect(16, (height - dot_size) / 2, dot_size, dot_size)
        )
        self._rec_dot.setWantsLayer_(True)
        dot_layer = self._rec_dot.layer()
        if dot_layer is not None:
            dot_layer.setBackgroundColor_(_hex_to_nscolor(STATE_COLORS["idle"]).CGColor())
            dot_layer.setCornerRadius_(dot_size / 2)
        content.addSubview_(self._rec_dot)

        # Timer
        self._timer_field = NSTextField.alloc().initWithFrame_(NSMakeRect(34, 16, 72, 24))
        self._timer_field.setBezeled_(False)
        self._timer_field.setDrawsBackground_(False)
        self._timer_field.setEditable_(False)
        self._timer_field.setSelectable_(False)
        self._timer_field.setStringValue_("00:00")
        self._timer_field.setFont_(NSFont.monospacedDigitSystemFontOfSize_weight_(14, 0))
        self._timer_field.setTextColor_(_hex_to_nscolor(TEXT_PRIMARY))
        content.addSubview_(self._timer_field)

        # Level bar
        self._level_bar = NSProgressIndicator.alloc().initWithFrame_(
            NSMakeRect(112, 22, 96, 12)
        )
        self._level_bar.setStyle_(0)  # bar
        self._level_bar.setMinValue_(0.0)
        self._level_bar.setMaxValue_(1.0)
        self._level_bar.setDoubleValue_(0.03)
        self._level_bar.setIndeterminate_(False)
        content.addSubview_(self._level_bar)

        # Action button
        self._target = _PanelTarget.alloc().initWithTkApp_actionCallback_(self._tk_app, self._on_action)
        btn_w, btn_h = 78.0, 32.0
        self._action_btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(width - btn_w - 14, (height - btn_h) / 2, btn_w, btn_h)
        )
        self._action_btn.setBezelStyle_(_NS_BEZEL_ROUNDED)
        self._action_btn.setTitle_("Start")
        self._action_btn.setTarget_(self._target)
        self._action_btn.setAction_("panelAction:")
        self._action_btn.setFont_(NSFont.systemFontOfSize_weight_(11, 0.6))
        content.addSubview_(self._action_btn)

        self._panel.setContentSize_(NSMakeSize(width, height))
        log.info("native_panel_created size=%sx%s", width, height)

    def _place_bottom_right(self, margin: int = 16) -> None:
        from AppKit import NSScreen

        screen = NSScreen.mainScreen()
        if screen is None:
            return
        frame = screen.visibleFrame()
        w = PANEL_W
        h = PANEL_H
        x = frame.origin.x + frame.size.width - w - margin
        y = frame.origin.y + margin + 48
        self._panel.setFrameOrigin_((x, y))

    def _set_rec_dot_color(self, hex_color: str) -> None:
        if self._rec_dot is None:
            return
        layer = self._rec_dot.layer()
        if layer is not None:
            layer.setBackgroundColor_(_hex_to_nscolor(hex_color).CGColor())

    def _configure_action_button(self, *, title: str, bg_hex: str) -> None:
        if self._action_btn is None:
            return
        self._action_btn.setTitle_(title)
        self._action_btn.setBezelColor_(_hex_to_nscolor(bg_hex))

    def show_recording(self) -> None:
        self._stopping = False
        self._recording = True
        self._visible = True
        self._start_ts = time.time()
        self._set_rec_dot_color(ACCENT_REC)
        self._configure_action_button(title="Stop", bg_hex=BTN_STOP)
        if self._action_btn is not None:
            self._action_btn.setEnabled_(True)
        self._timer_field.setStringValue_("00:00")
        self._place_bottom_right()
        self._panel.orderFrontRegardless()
        self._cancel_timer()
        self._tick_timer()
        log_event("native_panel_shown", mode="recording")

    def show_idle_ready(self) -> None:
        self._stopping = False
        self._recording = False
        self._visible = True
        self._start_ts = None
        self._set_rec_dot_color(STATE_COLORS["idle"])
        self._configure_action_button(title="Start", bg_hex=BTN_PRIMARY)
        if self._action_btn is not None:
            self._action_btn.setEnabled_(True)
        self._timer_field.setStringValue_("00:00")
        self._place_bottom_right()
        self._panel.orderFrontRegardless()
        self._cancel_timer()
        log_event("native_panel_shown", mode="idle")

    def show_stopping(self) -> None:
        """Immediate feedback after Stop — hide panel and ignore repeat clicks."""
        self._stopping = True
        self._recording = False
        self._visible = False
        self._start_ts = None
        self._cancel_timer()
        if self._action_btn is not None:
            self._action_btn.setEnabled_(False)
            self._action_btn.setTitle_("Stopping…")
        if self._panel is not None:
            self._panel.orderOut_(None)
        log_event("native_panel_stopping")

    def hide_panel(self) -> None:
        self._stopping = False
        self._visible = False
        self._cancel_timer()
        if self._panel is not None:
            self._panel.orderOut_(None)
        log_event("native_panel_hidden")

    def set_peak(self, peak: float) -> None:
        if not self._visible or self._level_bar is None:
            return
        peak = max(0.0, min(1.0, peak))
        self._level_bar.setDoubleValue_(peak)

    def _tick_timer(self) -> None:
        if not self._recording or self._start_ts is None or not self._visible:
            return
        elapsed = int(time.time() - self._start_ts)
        m, s = divmod(elapsed, 60)
        h, m = divmod(m, 60)
        text = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        if self._timer_field is not None:
            self._timer_field.setStringValue_(text)
        try:
            self._timer_job = self._tk_app.after(1000, self._tick_timer)
        except Exception:
            self._timer_job = None

    def _cancel_timer(self) -> None:
        if self._timer_job is not None:
            try:
                self._tk_app.after_cancel(self._timer_job)
            except Exception:
                pass
            self._timer_job = None
