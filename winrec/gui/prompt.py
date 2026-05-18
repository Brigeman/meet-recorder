"""Meeting prompt — modern accent card."""

import customtkinter as ctk

from winrec.gui.icons import load_logo_image
from winrec.gui.glass import GlassWindow, label
from winrec.gui.theme import (
    BTN_PRIMARY,
    BTN_PRIMARY_HOVER,
    BTN_QUIET,
    BTN_QUIET_HOVER,
    GLASS_ALPHA,
    PAD,
    PROMPT_H,
    PROMPT_W,
    TEXT_PRIMARY,
    TEXT_MUTED,
    TEXT_SECONDARY,
)

PROMPT_TITLE = "Похоже, идет звонок"


class MeetingPrompt(GlassWindow):
    def __init__(self, master, on_record, on_dismiss):
        super().__init__(master, PROMPT_W, PROMPT_H, corner_radius=22)
        self._on_record = on_record
        self._on_dismiss = on_dismiss
        self._app_name = ""
        self._fade_job = None
        self._build()

    def _build(self):
        c = self.content
        c.grid_columnconfigure(1, weight=1)
        c.grid_rowconfigure(1, weight=1)

        self._watermark_img = ctk.CTkImage(
            light_image=load_logo_image(28),
            dark_image=load_logo_image(28),
            size=(28, 28),
        )
        self._watermark = ctk.CTkLabel(c, text="", image=self._watermark_img, width=28)
        self._watermark.grid(row=0, column=0, sticky="nw", padx=(PAD, 6), pady=(PAD, 0))

        self._title = label(c, PROMPT_TITLE, bold=True, font_size=14)
        self._title.configure(text_color=TEXT_PRIMARY)
        self._title.grid(row=0, column=1, sticky="sw", padx=(0, 14), pady=(14, 0))

        self._subtitle = label(c, "", muted=True, font_size=11)
        self._subtitle.configure(text_color=TEXT_SECONDARY)
        self._subtitle.grid(row=1, column=1, sticky="nw", padx=(0, 14), pady=(2, 0))

        btn_row = ctk.CTkFrame(c, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=2, sticky="e", padx=12, pady=(10, 12))

        ctk.CTkButton(
            btn_row,
            text="Не сейчас",
            width=96,
            height=32,
            font=("Segoe UI Semibold", 10),
            fg_color=BTN_QUIET,
            hover_color=BTN_QUIET_HOVER,
            text_color=TEXT_MUTED,
            corner_radius=18,
            command=self._dismiss,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_row,
            text="Записать",
            width=96,
            height=32,
            font=("Segoe UI Semibold", 10),
            fg_color=BTN_PRIMARY,
            hover_color=BTN_PRIMARY_HOVER,
            corner_radius=18,
            command=self._record,
        ).pack(side="left")

    def show_for_candidate(self, app: str) -> None:
        self._app_name = app
        self._subtitle.configure(text=f"Записать встречу в {app}?")
        self._show_fade_in()

    def _show_fade_in(self) -> None:
        self.show_animated()
        try:
            self.attributes("-alpha", 0.0)
        except Exception:
            return
        self._fade(0.0)

    def _fade(self, alpha: float) -> None:
        if self._fade_job:
            self.after_cancel(self._fade_job)
            self._fade_job = None
        next_alpha = min(alpha + 0.18, GLASS_ALPHA)
        self.attributes("-alpha", next_alpha)
        if next_alpha < GLASS_ALPHA:
            self._fade_job = self.after(35, lambda: self._fade(next_alpha))

    def _dismiss(self):
        if self._fade_job:
            self.after_cancel(self._fade_job)
            self._fade_job = None
        self.hide_window()
        self._on_dismiss(self._app_name)

    def _record(self):
        if self._fade_job:
            self.after_cancel(self._fade_job)
            self._fade_job = None
        self.hide_window()
        self._on_record(self._app_name)
