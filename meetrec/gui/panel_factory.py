"""Factory for platform-specific recording panel and meeting prompt."""

from __future__ import annotations

import sys
from typing import Callable


def create_recording_panel(master, on_stop: Callable[[], None], on_start: Callable[[], None]):
    if sys.platform == "darwin":
        from meetrec.gui.native_panel_macos import NativePanel

        return NativePanel(master, on_stop, on_start)
    from meetrec.gui.panel import FloatingPanel

    return FloatingPanel(master, on_stop, on_start)


def create_meeting_prompt(master, on_record: Callable[[str], None], on_dismiss: Callable[[str], None]):
    if sys.platform == "darwin":
        from meetrec.gui.native_prompt_macos import NativeMeetingPrompt

        return NativeMeetingPrompt(master, on_record, on_dismiss)
    from meetrec.gui.prompt import MeetingPrompt

    return MeetingPrompt(master, on_record, on_dismiss)
