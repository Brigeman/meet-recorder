"""Settings window."""

import os
from tkinter import filedialog

import customtkinter as ctk

from winrec.config import AUDIO_FORMATS, save_config
from winrec.gui.theme import (
    BG_CARD,
    BG_CONTROL,
    BG_CONTROL_HOVER,
    BG_DARK,
    BG_INPUT,
    PAD,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, config: dict, on_save):
        super().__init__(master)
        self._cfg = dict(config)
        self._on_save = on_save
        self.title("Settings")
        self.geometry("380x280")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        card.grid(row=0, column=0, padx=PAD, pady=PAD, sticky="nsew")
        card.grid_columnconfigure(1, weight=1)

        rows = [
            ("Save to", 0),
            ("Format", 1),
            ("Prefix", 2),
            ("Threshold", 3),
            ("Web sustain (s)", 4),
            ("Desktop sustain (s)", 5),
        ]
        for label, r in rows:
            ctk.CTkLabel(
                card, text=label, font=("Segoe UI", 11), text_color=TEXT_SECONDARY
            ).grid(row=r, column=0, padx=14, pady=6, sticky="w")

        self._path_var = ctk.StringVar(value=self._cfg.get("recordings_dir", ""))
        pf = ctk.CTkFrame(card, fg_color="transparent")
        pf.grid(row=0, column=1, padx=(0, 12), pady=6, sticky="ew")
        pf.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(
            pf, textvariable=self._path_var, height=28, font=("Segoe UI", 10), fg_color=BG_INPUT
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            pf, text="…", width=28, height=28, command=self._pick_folder,
            fg_color=BG_CONTROL, hover_color=BG_CONTROL_HOVER,
        ).grid(row=0, column=1, padx=(4, 0))

        self._format_var = ctk.StringVar(value=self._cfg.get("audio_format", "wav"))
        ctk.CTkOptionMenu(
            card, values=AUDIO_FORMATS, variable=self._format_var, width=100, height=28,
            fg_color=BG_CONTROL, button_color=BG_CONTROL_HOVER,
        ).grid(row=1, column=1, padx=(0, 12), pady=6, sticky="w")

        self._prefix_var = ctk.StringVar(value=self._cfg.get("filename_prefix", "meeting"))
        ctk.CTkEntry(
            card, textvariable=self._prefix_var, height=28, width=120,
            fg_color=BG_INPUT,
        ).grid(row=2, column=1, padx=(0, 12), pady=6, sticky="w")

        self._threshold_var = ctk.StringVar(value=str(self._cfg.get("prompt_threshold", 70)))
        ctk.CTkEntry(
            card, textvariable=self._threshold_var, height=28, width=60, fg_color=BG_INPUT
        ).grid(row=3, column=1, padx=(0, 12), pady=6, sticky="w")

        self._web_sustain_var = ctk.StringVar(value=str(self._cfg.get("web_sustain_seconds", 2.5)))
        ctk.CTkEntry(
            card, textvariable=self._web_sustain_var, height=28, width=60, fg_color=BG_INPUT
        ).grid(row=4, column=1, padx=(0, 12), pady=6, sticky="w")

        self._desktop_sustain_var = ctk.StringVar(
            value=str(self._cfg.get("desktop_sustain_seconds", 7.0))
        )
        ctk.CTkEntry(
            card, textvariable=self._desktop_sustain_var, height=28, width=60, fg_color=BG_INPUT
        ).grid(row=5, column=1, padx=(0, 12), pady=6, sticky="w")

        ctk.CTkButton(
            self, text="Save", command=self._save,
            fg_color=BG_CONTROL, hover_color=BG_CONTROL_HOVER,
        ).grid(row=1, column=0, pady=(0, PAD))

    def _pick_folder(self):
        path = filedialog.askdirectory(initialdir=self._path_var.get())
        if path:
            self._path_var.set(path)

    def _save(self):
        try:
            self._cfg["prompt_threshold"] = int(self._threshold_var.get())
            self._cfg["web_sustain_seconds"] = float(self._web_sustain_var.get())
            self._cfg["desktop_sustain_seconds"] = float(self._desktop_sustain_var.get())
        except ValueError:
            pass
        self._cfg["recordings_dir"] = self._path_var.get()
        self._cfg["audio_format"] = self._format_var.get()
        self._cfg["filename_prefix"] = self._prefix_var.get().strip()
        save_config(self._cfg)
        self._on_save(self._cfg)
        self.destroy()
