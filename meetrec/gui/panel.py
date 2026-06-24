"""Floating recording capsule — modern accent style."""

import time

import customtkinter as ctk

from meetrec.gui.icons import load_logo_image
from meetrec.gui.glass import GlassWindow
from meetrec.gui.theme import (
    ACCENT_REC,
    ACCENT_REC_HOVER,
    BTN_PRIMARY,
    BTN_PRIMARY_HOVER,
    BTN_STOP,
    BTN_STOP_HOVER,
    GLASS_SURFACE,
    PANEL_H,
    PANEL_W,
    STATE_COLORS,
    TEXT_PRIMARY,
)
from meetrec.gui.waveform import MiniWaveform


class FloatingPanel(GlassWindow):
    def __init__(self, master, on_stop, on_start):
        # Solid window (no alpha) — much smoother on Windows.
        super().__init__(master, PANEL_W, PANEL_H, corner_radius=28, use_alpha=False)
        self._on_stop = on_stop
        self._on_start = on_start
        self._recording = False
        self._visible = False
        self._start_ts: float | None = None
        self._timer_job = None
        self._pulse_job = None
        self._pulse_phase = 0.0
        self._build()

    @property
    def is_visible(self) -> bool:
        return self._visible

    def _build(self):
        c = self.content
        c.configure(fg_color=GLASS_SURFACE)
        c.grid_columnconfigure(2, weight=1)
        c.grid_rowconfigure(0, weight=1)

        self._logo_img = ctk.CTkImage(
            light_image=load_logo_image(14),
            dark_image=load_logo_image(14),
            size=(14, 14),
        )
        self._logo = ctk.CTkLabel(c, text="", image=self._logo_img, width=14)
        self._logo.grid(row=0, column=0, padx=(14, 0), pady=21, sticky="n")

        self._rec_dot = ctk.CTkFrame(c, width=10, height=10, corner_radius=5, fg_color=STATE_COLORS["idle"])
        self._rec_dot.grid(row=0, column=0, padx=(16, 10), pady=30, sticky="s")

        self._timer = ctk.CTkLabel(
            c,
            text="00:00",
            font=("Consolas", 14),
            text_color=TEXT_PRIMARY,
            width=66,
        )
        self._timer.grid(row=0, column=1, padx=(0, 10))

        self._wave = MiniWaveform(c)
        self._wave.grid(row=0, column=2, sticky="w")

        self._action_btn = ctk.CTkButton(
            c,
            text="Start",
            width=78,
            height=32,
            font=("Segoe UI Semibold", 10),
            fg_color=BTN_PRIMARY,
            hover_color=BTN_PRIMARY_HOVER,
            corner_radius=18,
            command=self._action,
        )
        self._action_btn.grid(row=0, column=3, padx=(10, 14))

    def show_recording(self) -> None:
        self._recording = True
        self._visible = True
        self._start_ts = time.time()
        self._rec_dot.configure(fg_color=ACCENT_REC)
        self._action_btn.configure(text="Stop")
        self._action_btn.configure(fg_color=BTN_STOP, hover_color=BTN_STOP_HOVER)
        self.show_animated()
        self._tick_timer()
        self._tick_pulse()

    def show_idle_ready(self) -> None:
        self._recording = False
        self._visible = True
        self._start_ts = None
        self._rec_dot.configure(fg_color=STATE_COLORS["idle"])
        self._timer.configure(text="00:00")
        self._action_btn.configure(text="Start")
        self._action_btn.configure(fg_color=BTN_PRIMARY, hover_color=BTN_PRIMARY_HOVER)
        self.show_animated()
        self._cancel_timer()
        self._cancel_pulse()

    def hide_panel(self) -> None:
        self._visible = False
        self._cancel_timer()
        self._cancel_pulse()
        self.hide_window()

    def set_peak(self, peak: float) -> None:
        if self._visible:
            self._wave.set_peak(peak)

    def _action(self):
        if self._recording:
            self._on_stop()
        else:
            self._on_start()

    def _tick_timer(self):
        if not self._recording or self._start_ts is None or not self._visible:
            return
        elapsed = int(time.time() - self._start_ts)
        m, s = divmod(elapsed, 60)
        h, m = divmod(m, 60)
        text = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        self._timer.configure(text=text)
        self._timer_job = self.after(1000, self._tick_timer)

    def _cancel_timer(self):
        if self._timer_job:
            self.after_cancel(self._timer_job)
            self._timer_job = None

    def _tick_pulse(self):
        if not self._recording or not self._visible:
            return
        self._pulse_phase = (self._pulse_phase + 0.2) % 1.0
        if self._pulse_phase < 0.5:
            color = _blend_hex(ACCENT_REC, ACCENT_REC_HOVER, self._pulse_phase * 2.0)
        else:
            color = _blend_hex(ACCENT_REC_HOVER, ACCENT_REC, (self._pulse_phase - 0.5) * 2.0)
        self._rec_dot.configure(fg_color=color)
        self._pulse_job = self.after(160, self._tick_pulse)

    def _cancel_pulse(self):
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None
        self._pulse_phase = 0.0


def _blend_hex(c1: str, c2: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02X}{g:02X}{b:02X}"


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    if len(value) != 6:
        return (0, 0, 0)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
