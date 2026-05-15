"""Shared glass-style floating windows."""

import tkinter as tk

import customtkinter as ctk

from winrec.gui.theme import (
    GLASS_ALPHA,
    GLASS_BG,
    GLASS_BORDER,
    GLASS_SHADOW,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


class GlassWindow(ctk.CTkToplevel):
    """Borderless topmost window with capsule/card chrome."""

    def __init__(self, master, width: int, height: int, corner_radius: int = 16):
        super().__init__(master)
        self._width = width
        self._height = height
        self._corner = corner_radius
        self._drag_x = 0
        self._drag_y = 0

        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", GLASS_ALPHA)
        except tk.TclError:
            pass
        self.configure(fg_color=GLASS_SHADOW)
        self.geometry(f"{width}x{height}")

        self._outer = ctk.CTkFrame(
            self,
            width=width,
            height=height,
            fg_color=GLASS_BG,
            corner_radius=corner_radius,
            border_width=1,
            border_color=GLASS_BORDER,
        )
        self._outer.pack(fill="both", expand=True)
        self._outer.pack_propagate(False)

        self._content = ctk.CTkFrame(self._outer, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=1, pady=1)

        for w in (self._outer, self._content):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

    @property
    def content(self) -> ctk.CTkFrame:
        return self._content

    def place_bottom_right(self, margin: int = 16) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = sw - self._width - margin
        y = sh - self._height - margin - 48
        self.geometry(f"+{x}+{y}")

    def show_animated(self) -> None:
        self.place_bottom_right()
        self.deiconify()
        self.lift()

    def hide_window(self) -> None:
        self.withdraw()

    def _start_drag(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_drag(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")


def label(parent, text: str, *, muted: bool = False, font_size: int = 12, bold: bool = False) -> ctk.CTkLabel:
    weight = "bold" if bold else "normal"
    family = "Segoe UI Semibold" if bold else "Segoe UI"
    return ctk.CTkLabel(
        parent,
        text=text,
        font=(family, font_size, weight),
        text_color=TEXT_MUTED if muted else TEXT_PRIMARY,
        anchor="w",
    )
