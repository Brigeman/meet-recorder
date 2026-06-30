"""Native macOS menu bar tray via NSStatusItem (pyobjc)."""

from __future__ import annotations

import io
import logging
import subprocess
from typing import Callable

import objc
from Foundation import NSObject
from PIL import Image

log = logging.getLogger(__name__)

_MENU_BAR_ICON_SIZE = 18


def _pil_to_nsimage(image: Image.Image):
    from AppKit import NSImage, NSMakeSize
    from Foundation import NSData

    img = image.convert("RGBA")
    if img.size != (_MENU_BAR_ICON_SIZE, _MENU_BAR_ICON_SIZE):
        img = img.resize((_MENU_BAR_ICON_SIZE, _MENU_BAR_ICON_SIZE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = NSData(buf.getvalue())
    ns_image = NSImage.alloc().initWithData_(data)
    if ns_image:
        ns_image.setSize_(NSMakeSize(_MENU_BAR_ICON_SIZE, _MENU_BAR_ICON_SIZE))
        ns_image.setTemplate_(True)
    return ns_image


class _TrayMenuTarget(NSObject):
    """ObjC target for NSMenuItem actions; forwards to Tk via after(0, ...)."""

    def initWithTkApp_callbacks_(self, tk_app, callbacks):
        self = objc.super(_TrayMenuTarget, self).init()
        if self is None:
            return None
        self._tk_app = tk_app
        self._callbacks = callbacks
        return self

    def toggleRecord_(self, sender):  # noqa: N802 - ObjC selector
        self._tk_app.after(0, self._callbacks["toggle"])

    def openFolder_(self, sender):
        self._tk_app.after(0, self._callbacks["open_folder"])

    def openSettings_(self, sender):
        self._tk_app.after(0, self._callbacks["settings"])

    def quitApp_(self, sender):
        self._tk_app.after(0, self._callbacks["quit"])


class MacOSTray:
    """NSStatusItem tray; mimics pystray.Icon surface used by WinRecApp."""

    def __init__(
        self,
        tk_app,
        name: str,
        icon: Image.Image,
        *,
        on_toggle_record: Callable[[], None],
        on_open_folder: Callable[[], None],
        on_settings: Callable[[], None],
        on_quit: Callable[[], None],
        recording: bool = False,
    ):
        from AppKit import NSMenu, NSMenuItem, NSStatusBar, NSVariableStatusItemLength

        self._tk_app = tk_app
        self._name = name
        self._recording = recording
        self._icon_image = icon
        self._status_item = None
        self._toggle_item = None

        callbacks = {
            "toggle": on_toggle_record,
            "open_folder": on_open_folder,
            "settings": on_settings,
            "quit": on_quit,
        }
        self._menu_target = _TrayMenuTarget.alloc().initWithTkApp_callbacks_(tk_app, callbacks)

        status_bar = NSStatusBar.systemStatusBar()
        self._status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)
        self._status_item.setToolTip_(name)

        btn = self._status_item.button()
        if btn:
            ns_img = _pil_to_nsimage(icon)
            if ns_img:
                btn.setImage_(ns_img)

        menu = NSMenu.alloc().init()
        self._toggle_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            self._toggle_title(),
            "toggleRecord:",
            "",
        )
        self._toggle_item.setTarget_(self._menu_target)
        menu.addItem_(self._toggle_item)

        for title, action in (
            ("Open recordings folder", "openFolder:"),
            ("Settings", "openSettings:"),
        ):
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
            item.setTarget_(self._menu_target)
            menu.addItem_(item)

        menu.addItem_(NSMenuItem.separatorItem())

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", "quitApp:", "")
        quit_item.setTarget_(self._menu_target)
        menu.addItem_(quit_item)

        self._status_item.setMenu_(menu)

    def _toggle_title(self) -> str:
        return "Stop recording" if self._recording else "Start recording"

    @property
    def icon(self) -> Image.Image:
        return self._icon_image

    @icon.setter
    def icon(self, value: Image.Image) -> None:
        self._icon_image = value
        if not self._status_item:
            return
        btn = self._status_item.button()
        if btn:
            ns_img = _pil_to_nsimage(value)
            if ns_img:
                btn.setImage_(ns_img)

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        if self._toggle_item:
            self._toggle_item.setTitle_(self._toggle_title())

    def notify(self, title: str, message: str) -> None:
        try:
            esc_title = title.replace("\\", "\\\\").replace('"', '\\"')
            esc_msg = message.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{esc_msg}" with title "{esc_title}"',
                ],
                check=False,
            )
        except Exception:
            log.debug("macOS tray notify failed", exc_info=True)

    def stop(self) -> None:
        if not self._status_item:
            return
        from AppKit import NSStatusBar

        NSStatusBar.systemStatusBar().removeStatusItem_(self._status_item)
        self._status_item = None
        self._toggle_item = None
