"""Mini waveform — single Canvas redraw (lightweight)."""

import tkinter as tk

import customtkinter as ctk

from winrec.gui.theme import ACCENT_REC, GLASS_BG, TEXT_MUTED

BAR_COUNT = 12
BAR_W = 3
BAR_GAP = 2
CANVAS_W = BAR_COUNT * (BAR_W + BAR_GAP)
CANVAS_H = 22
DRAW_MS = 100


class MiniWaveform(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._levels = [0.04] * BAR_COUNT
        self._draw_job = None
        self._canvas = tk.Canvas(
            self,
            width=CANVAS_W,
            height=CANVAS_H,
            bg=GLASS_BG,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack()
        self._draw_bars()

    def set_peak(self, peak: float) -> None:
        peak = max(0.0, min(1.0, peak))
        self._levels.pop(0)
        self._levels.append(peak)
        if self._draw_job is None:
            self._draw_job = self.after(DRAW_MS, self._draw_bars)

    def _draw_bars(self) -> None:
        self._draw_job = None
        c = self._canvas
        c.delete("all")
        x = 1
        for level in self._levels:
            h = max(3, int(3 + level * 16))
            y0 = CANVAS_H - 2 - h
            color = ACCENT_REC if level > 0.72 else TEXT_MUTED
            c.create_rectangle(x, y0, x + BAR_W, CANVAS_H - 2, fill=color, outline="")
            x += BAR_W + BAR_GAP
