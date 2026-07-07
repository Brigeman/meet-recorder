"""Native macOS meeting prompt — NSPanel with Record / Dismiss buttons."""

from __future__ import annotations

import logging
from typing import Callable

import objc
from Foundation import NSObject

from meetrec.gui.theme import (
    BTN_PRIMARY,
    BTN_QUIET,
    GLASS_BG,
    GLASS_BORDER,
    PROMPT_H,
    PROMPT_W,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from meetrec.logging_util import log_event

log = logging.getLogger(__name__)

PROMPT_TITLE = "Похоже, идет звонок"

_NS_STATUS_WINDOW_LEVEL = 25
_NS_CAN_JOIN_ALL_SPACES = 1 << 0
_NS_STATIONARY = 1 << 4
_NS_FULLSCREEN_AUXILIARY = 1 << 8
_NS_BEZEL_ROUNDED = 1


def _hex_to_nscolor(hex_color: str, alpha: float = 1.0):
    from AppKit import NSColor

    value = hex_color.lstrip("#")
    if len(value) != 6:
        return NSColor.whiteColor()
    r = int(value[0:2], 16) / 255.0
    g = int(value[2:4], 16) / 255.0
    b = int(value[4:6], 16) / 255.0
    return NSColor.colorWithRed_green_blue_alpha_(r, g, b, alpha)


class _PromptTarget(NSObject):
    def initWithPrompt_callbacks_(self, prompt, callbacks):
        self = objc.super(_PromptTarget, self).init()
        if self is None:
            return None
        self._prompt = prompt
        self._callbacks = callbacks
        return self

    def record_(self, sender):  # noqa: N802
        log.info("native_prompt_record_clicked")
        self._prompt._tk_app._post_to_ui(self._callbacks["record"])

    def dismiss_(self, sender):
        log.info("native_prompt_dismiss_clicked")
        self._prompt._tk_app._post_to_ui(self._callbacks["dismiss"])


class NativeMeetingPrompt:
    """AppKit prompt card; replaces Tk MeetingPrompt on macOS."""

    def __init__(
        self,
        tk_app,
        on_record: Callable[[str], None],
        on_dismiss: Callable[[str], None],
    ):
        self._tk_app = tk_app
        self._on_record = on_record
        self._on_dismiss = on_dismiss
        self._app_name = ""
        self._panel = None
        self._subtitle = None
        self._target = None
        self._build()

    def _build(self) -> None:
        from AppKit import (
            NSBackingStoreBuffered,
            NSButton,
            NSColor,
            NSFont,
            NSMakeRect,
            NSPanel,
            NSTextField,
            NSView,
            NSWindowStyleMaskBorderless,
        )
        from Foundation import NSMakeSize

        width, height = PROMPT_W, PROMPT_H
        style = int(NSWindowStyleMaskBorderless)
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
        self._panel.setBecomesKeyOnlyIfNeeded_(False)
        self._panel.setMovableByWindowBackground_(True)

        content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        content.setWantsLayer_(True)
        layer = content.layer()
        if layer is not None:
            layer.setBackgroundColor_(_hex_to_nscolor(GLASS_BG).CGColor())
            layer.setCornerRadius_(16.0)
            layer.setBorderWidth_(1.0)
            layer.setBorderColor_(_hex_to_nscolor(GLASS_BORDER).CGColor())
        self._panel.setContentView_(content)

        title = NSTextField.alloc().initWithFrame_(NSMakeRect(16, height - 36, width - 32, 22))
        title.setBezeled_(False)
        title.setDrawsBackground_(False)
        title.setEditable_(False)
        title.setSelectable_(False)
        title.setStringValue_(PROMPT_TITLE)
        title.setFont_(NSFont.boldSystemFontOfSize_(14))
        title.setTextColor_(_hex_to_nscolor(TEXT_PRIMARY))
        content.addSubview_(title)

        self._subtitle = NSTextField.alloc().initWithFrame_(NSMakeRect(16, height - 58, width - 32, 18))
        self._subtitle.setBezeled_(False)
        self._subtitle.setDrawsBackground_(False)
        self._subtitle.setEditable_(False)
        self._subtitle.setSelectable_(False)
        self._subtitle.setStringValue_("")
        self._subtitle.setFont_(NSFont.systemFontOfSize_(11))
        self._subtitle.setTextColor_(_hex_to_nscolor(TEXT_SECONDARY))
        content.addSubview_(self._subtitle)

        callbacks = {
            "record": self._do_record,
            "dismiss": self._do_dismiss,
        }
        self._target = _PromptTarget.alloc().initWithPrompt_callbacks_(self, callbacks)

        dismiss_btn = NSButton.alloc().initWithFrame_(NSMakeRect(width - 210, 14, 96, 32))
        dismiss_btn.setBezelStyle_(_NS_BEZEL_ROUNDED)
        dismiss_btn.setTitle_("Не сейчас")
        dismiss_btn.setTarget_(self._target)
        dismiss_btn.setAction_("dismiss:")
        dismiss_btn.setEnabled_(True)
        dismiss_btn.setBezelColor_(_hex_to_nscolor(BTN_QUIET))
        dismiss_btn.setFont_(NSFont.systemFontOfSize_weight_(11, 0.5))
        content.addSubview_(dismiss_btn)

        record_btn = NSButton.alloc().initWithFrame_(NSMakeRect(width - 108, 14, 96, 32))
        record_btn.setBezelStyle_(_NS_BEZEL_ROUNDED)
        record_btn.setTitle_("Записать")
        record_btn.setTarget_(self._target)
        record_btn.setAction_("record:")
        record_btn.setEnabled_(True)
        record_btn.setBezelColor_(_hex_to_nscolor(BTN_PRIMARY))
        record_btn.setFont_(NSFont.systemFontOfSize_weight_(11, 0.6))
        content.addSubview_(record_btn)

        self._panel.setContentSize_(NSMakeSize(width, height))
        log.info("native_prompt_created")

    def _place_bottom_right(self, margin: int = 16) -> None:
        from AppKit import NSScreen

        screen = NSScreen.mainScreen()
        if screen is None:
            return
        frame = screen.visibleFrame()
        w = PROMPT_W
        h = PROMPT_H
        x = frame.origin.x + frame.size.width - w - margin
        y = frame.origin.y + margin + 48
        self._panel.setFrameOrigin_((x, y))

    def show_for_candidate(self, app: str) -> None:
        from AppKit import NSApp

        self._app_name = app
        if self._subtitle is not None:
            self._subtitle.setStringValue_(f"Записать встречу в {app}?")
        self._place_bottom_right()
        self._panel.orderFrontRegardless()
        self._panel.makeKeyAndOrderFront_(None)
        ns_app = NSApp.sharedApplication()
        if ns_app is not None:
            ns_app.activateIgnoringOtherApps_(True)
        log_event("native_prompt_shown", app=app)

    def hide_window(self) -> None:
        if self._panel is not None:
            self._panel.orderOut_(None)

    def _do_record(self) -> None:
        app = self._app_name
        self.hide_window()
        log_event("native_prompt_record", app=app)
        self._on_record(app)

    def _do_dismiss(self) -> None:
        app = self._app_name
        self.hide_window()
        log_event("native_prompt_dismiss", app=app)
        self._on_dismiss(app)
