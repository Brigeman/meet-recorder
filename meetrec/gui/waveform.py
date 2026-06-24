"""Mini waveform with eased animation."""

import tkinter as tk

import customtkinter as ctk

from meetrec.gui.theme import ACCENT_PRIMARY, ACCENT_SOFT, GLASS_BG, TEXT_MUTED

BAR_COUNT = 16
BAR_W = 4
BAR_GAP = 2
CANVAS_W = BAR_COUNT * BAR_W + (BAR_COUNT - 1) * BAR_GAP + 2
CANVAS_H = 22
DRAW_MS = 60
EASE = 0.35


class MiniWaveform(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._levels = [0.03] * BAR_COUNT
        self._targets = [0.03] * BAR_COUNT
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
        self._targets.pop(0)
        self._targets.append(peak)
        if self._draw_job is None:
            self._draw_job = self.after(DRAW_MS, self._draw_bars)

    def _draw_bars(self) -> None:
        self._draw_job = self.after(DRAW_MS, self._draw_bars)
        c = self._canvas
        c.delete("all")
        x = 1
        movement = 0.0
        for idx, target in enumerate(self._targets):
            level = self._levels[idx]
            eased = level + (target - level) * EASE
            self._levels[idx] = eased
            movement += abs(target - eased)
            h = max(3, int(3 + eased * 16))
            y0 = CANVAS_H - 2 - h
            if eased > 0.72:
                color = ACCENT_SOFT
            elif eased > 0.38:
                color = ACCENT_PRIMARY
            else:
                color = _blend_hex(TEXT_MUTED, GLASS_BG, 0.7)
            c.create_rectangle(x, y0, x + BAR_W, CANVAS_H - 2, fill=color, outline="")
            x += BAR_W + BAR_GAP
        if movement < 0.01 and max(self._targets) < 0.06:
            self.after_cancel(self._draw_job)
            self._draw_job = None


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
