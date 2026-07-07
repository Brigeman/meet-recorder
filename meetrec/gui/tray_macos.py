"""Native macOS menu bar tray via NSStatusItem (pyobjc)."""

from __future__ import annotations

import io
import logging
import subprocess
from typing import Callable

import objc
from Foundation import NSObject
from PIL import Image

try:
    from AppKit import NSImageLeft
except ImportError:  # pragma: no cover - non-macOS
    NSImageLeft = 1

log = logging.getLogger(__name__)

_MENU_BAR_ICON_SIZE = 18


def _pil_to_nsimage(image: Image.Image, size: int = _MENU_BAR_ICON_SIZE):
    from AppKit import NSImage, NSMakeSize
    from Foundation import NSData

    img = image.convert("RGBA")
    if img.size != (size, size):
        img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = NSData(buf.getvalue())
    ns_image = NSImage.alloc().initWithData_(data)
    if ns_image:
        ns_image.setSize_(NSMakeSize(_MENU_BAR_ICON_SIZE, _MENU_BAR_ICON_SIZE))
        # Colored logo — do not use template mode (renders invisible on light menu bar).
        ns_image.setTemplate_(False)
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
        self._tk_app._post_to_ui(self._callbacks["toggle"])

    def openFolder_(self, sender):
        self._tk_app._post_to_ui(self._callbacks["open_folder"])

    def openSettings_(self, sender):
        self._tk_app._post_to_ui(self._callbacks["settings"])

    def quitApp_(self, sender):
        self._tk_app._post_to_ui(self._callbacks["quit"])


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

        # Tk already owns NSApplication; do not change activation policy here —
        # setActivationPolicy(Accessory) caused silent exits when SetupWizard opened.
        from AppKit import NSApplication

        app = NSApplication.sharedApplication()
        # Menu-bar-only: hide Dock icon; safe now that SetupWizard no longer auto-opens on startup.
        if app.activationPolicy() != 1:
            app.setActivationPolicy_(1)

        self._tk_app = tk_app
        self._name = name
        self._recording = recording
        self._icon_image = icon
        self._status_item = None
        self._toggle_item = None
        self._menu = None
        self._icon_state: str | None = None
        self._ns_image_monitoring = None
        self._ns_image_recording = None

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
            self._apply_icon(btn, icon, state="monitoring")
            btn.setHidden_(False)
            btn.setEnabled_(True)
        else:
            log.warning("macos_tray_button_missing")
        log.info("macos_tray_created title=%s", name)

        self._menu = NSMenu.alloc().init()
        self._toggle_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            self._toggle_title(),
            "toggleRecord:",
            "",
        )
        self._toggle_item.setTarget_(self._menu_target)
        self._menu.addItem_(self._toggle_item)

        for title, action in (
            ("Open recordings folder", "openFolder:"),
            ("Settings", "openSettings:"),
        ):
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
            item.setTarget_(self._menu_target)
            self._menu.addItem_(item)

        self._menu.addItem_(NSMenuItem.separatorItem())

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", "quitApp:", "")
        quit_item.setTarget_(self._menu_target)
        self._menu.addItem_(quit_item)

        self._status_item.setMenu_(self._menu)

    def _apply_icon(self, btn, image: Image.Image, *, state: str) -> None:
        if state == self._icon_state and state == "monitoring" and self._ns_image_monitoring is not None:
            btn.setImage_(self._ns_image_monitoring)
        elif state == self._icon_state and state == "recording" and self._ns_image_recording is not None:
            btn.setImage_(self._ns_image_recording)
        else:
            ns_img = _pil_to_nsimage(image, size=_MENU_BAR_ICON_SIZE)
            if not ns_img:
                return
            if state == "recording":
                self._ns_image_recording = ns_img
            else:
                self._ns_image_monitoring = ns_img
            btn.setImage_(ns_img)
            self._icon_state = state
        btn.setImagePosition_(NSImageLeft)
        btn.setTitle_("")

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
        if not btn:
            return
        state = "recording" if self._recording else "monitoring"
        if state == self._icon_state:
            return
        self._apply_icon(btn, value, state=state)

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        if self._toggle_item:
            self._toggle_item.setTitle_(self._toggle_title())
        if not self._status_item:
            return
        btn = self._status_item.button()
        if btn and self._icon_image is not None:
            state = "recording" if recording else "monitoring"
            if state != self._icon_state:
                from meetrec.gui.icons import make_tray_icon

                self._apply_icon(
                    btn,
                    make_tray_icon(state, size=_MENU_BAR_ICON_SIZE),
                    state=state,
                )

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
