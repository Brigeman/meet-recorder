"""Meeting prompt — glass card 320×92."""

import customtkinter as ctk

from winrec.gui.glass import GlassWindow, label
from winrec.gui.theme import (
    BTN_PRIMARY,
    BTN_PRIMARY_HOVER,
    BTN_QUIET,
    BTN_QUIET_HOVER,
    PROMPT_H,
    PROMPT_W,
)

PROMPT_TITLE = "Похоже, звонок — записать?"


class MeetingPrompt(GlassWindow):
    def __init__(self, master, on_record, on_dismiss):
        super().__init__(master, PROMPT_W, PROMPT_H, corner_radius=14)
        self._on_record = on_record
        self._on_dismiss = on_dismiss
        self._app_name = ""
        self._build()

    def _build(self):
        c = self.content
        c.grid_columnconfigure(0, weight=1)

        self._title = label(c, PROMPT_TITLE, bold=True, font_size=12)
        self._title.grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(10, 0))

        self._subtitle = label(c, "", muted=True, font_size=10)
        self._subtitle.grid(row=1, column=0, columnspan=2, sticky="w", padx=14, pady=(2, 0))

        btn_row = ctk.CTkFrame(c, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=2, sticky="e", padx=10, pady=(6, 8))

        ctk.CTkButton(
            btn_row,
            text="Не сейчас",
            width=88,
            height=26,
            font=("Segoe UI", 10),
            fg_color=BTN_QUIET,
            hover_color=BTN_QUIET_HOVER,
            corner_radius=8,
            command=self._dismiss,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_row,
            text="Записать",
            width=80,
            height=26,
            font=("Segoe UI", 10),
            fg_color=BTN_PRIMARY,
            hover_color=BTN_PRIMARY_HOVER,
            corner_radius=8,
            command=self._record,
        ).pack(side="left")

    def show_for_candidate(self, app: str) -> None:
        self._app_name = app
        self._subtitle.configure(text=f"Возможно, встреча в {app}")
        self.show_animated()

    def _dismiss(self):
        self.hide_window()
        self._on_dismiss(self._app_name)

    def _record(self):
        self.hide_window()
        self._on_record(self._app_name)
