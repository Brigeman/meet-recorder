"""Mini waveform bar widget."""

import customtkinter as ctk

from winrec.gui.theme import ACCENT_REC, TEXT_MUTED

BAR_COUNT = 14


class MiniWaveform(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._bars: list[ctk.CTkFrame] = []
        self._levels = [0.05] * BAR_COUNT
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True)
        for i in range(BAR_COUNT):
            bar = ctk.CTkFrame(
                inner,
                width=3,
                height=8,
                fg_color=TEXT_MUTED,
                corner_radius=1,
            )
            bar.pack(side="left", padx=1, pady=4)
            self._bars.append(bar)

    def set_peak(self, peak: float) -> None:
        peak = max(0.0, min(1.0, peak))
        self._levels.pop(0)
        self._levels.append(peak)
        for bar, level in zip(self._bars, self._levels):
            h = max(4, int(4 + level * 20))
            color = ACCENT_REC if level > 0.75 else TEXT_MUTED
            bar.configure(height=h, fg_color=color)
