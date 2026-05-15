"""Floating recording capsule — 360×48."""

import time

import customtkinter as ctk

from winrec.gui.glass import GlassWindow
from winrec.gui.theme import (
    ACCENT_REC,
    BTN_STOP,
    BTN_STOP_HOVER,
    PANEL_H,
    PANEL_W,
    STATE_COLORS,
    TEXT_PRIMARY,
)
from winrec.gui.waveform import MiniWaveform


class FloatingPanel(GlassWindow):
    def __init__(self, master, on_stop, on_start):
        super().__init__(master, PANEL_W, PANEL_H, corner_radius=24)
        self._on_stop = on_stop
        self._on_start = on_start
        self._recording = False
        self._start_ts: float | None = None
        self._timer_job = None
        self._build()

    def _build(self):
        c = self.content
        c.grid_columnconfigure(2, weight=1)

        self._rec_dot = ctk.CTkFrame(c, width=8, height=8, corner_radius=4, fg_color=STATE_COLORS["idle"])
        self._rec_dot.grid(row=0, column=0, padx=(14, 8), pady=20)

        self._timer = ctk.CTkLabel(
            c,
            text="00:00",
            font=("Consolas", 11),
            text_color=TEXT_PRIMARY,
            width=52,
        )
        self._timer.grid(row=0, column=1, padx=(0, 8))

        self._wave = MiniWaveform(c, width=120, height=32)
        self._wave.grid(row=0, column=2, sticky="w")

        self._action_btn = ctk.CTkButton(
            c,
            text="Stop",
            width=64,
            height=28,
            font=("Segoe UI Semibold", 10),
            fg_color=BTN_STOP,
            hover_color=BTN_STOP_HOVER,
            corner_radius=14,
            command=self._action,
        )
        self._action_btn.grid(row=0, column=3, padx=(8, 12))

    def show_recording(self) -> None:
        self._recording = True
        self._start_ts = time.time()
        self._rec_dot.configure(fg_color=ACCENT_REC)
        self._action_btn.configure(text="Stop")
        self.show_animated()
        self._tick_timer()

    def show_idle_ready(self) -> None:
        self._recording = False
        self._start_ts = None
        self._rec_dot.configure(fg_color=STATE_COLORS["idle"])
        self._timer.configure(text="00:00")
        self._action_btn.configure(text="Start")
        self.show_animated()
        self._cancel_timer()

    def hide_panel(self) -> None:
        self._cancel_timer()
        self.hide_window()

    def set_peak(self, peak: float) -> None:
        self._wave.set_peak(peak)

    def _action(self):
        if self._recording:
            self._on_stop()
        else:
            self._on_start()

    def _tick_timer(self):
        if not self._recording or self._start_ts is None:
            return
        elapsed = int(time.time() - self._start_ts)
        m, s = divmod(elapsed, 60)
        h, m = divmod(m, 60)
        if h:
            self._timer.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        else:
            self._timer.configure(text=f"{m:02d}:{s:02d}")
        self._timer_job = self.after(500, self._tick_timer)

    def _cancel_timer(self):
        if self._timer_job:
            self.after_cancel(self._timer_job)
            self._timer_job = None
