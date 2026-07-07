"""Settings window."""

import os
import sys
import webbrowser
from tkinter import filedialog

import customtkinter as ctk

from meetrec import autostart
from meetrec.calls.pairing import PairingError, apply_pairing_to_config
from meetrec.config import AUDIO_FORMATS, save_config
from meetrec.gui.theme import (
    ACCENT_PRIMARY,
    ACCENT_PRIMARY_HOVER,
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
    def __init__(
        self,
        master,
        config: dict,
        on_save,
        on_reset_pairing=None,
        on_pairing_complete=None,
    ):
        super().__init__(master)
        self._cfg = dict(config)
        self._on_save = on_save
        self._on_reset_pairing = on_reset_pairing
        self._on_pairing_complete = on_pairing_complete
        self._paired = bool(
            self._cfg.get("calls_setup_completed") and self._cfg.get("calls_device_token")
        )
        self.title("Settings")
        self.geometry("420x520" if not self._paired else "420x430")
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

        self._autostart_var = ctk.BooleanVar(value=self._cfg.get("start_with_windows", True))
        ctk.CTkLabel(
            card, text="Start with Windows", font=("Segoe UI", 11), text_color=TEXT_SECONDARY
        ).grid(row=6, column=0, padx=14, pady=(8, 6), sticky="w")
        ctk.CTkSwitch(
            card,
            text="Enable",
            variable=self._autostart_var,
            onvalue=True,
            offvalue=False,
            fg_color=ACCENT_PRIMARY,
            progress_color=ACCENT_PRIMARY,
            button_color=TEXT_PRIMARY,
            button_hover_color=TEXT_SECONDARY,
            text_color=TEXT_PRIMARY,
        ).grid(row=6, column=1, padx=(0, 12), pady=(8, 6), sticky="w")

        ctk.CTkLabel(
            card,
            text="Calls",
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY,
        ).grid(row=7, column=0, padx=14, pady=(8, 6), sticky="w")
        calls_frame = ctk.CTkFrame(card, fg_color="transparent")
        calls_frame.grid(row=7, column=1, padx=(0, 12), pady=(8, 6), sticky="ew")
        calls_frame.grid_columnconfigure(0, weight=1)

        if self._paired:
            status = "ПК уже привязан к Calls"
        elif self._cfg.get("calls_setup_skipped"):
            status = "Calls не подключён"
        else:
            status = "Calls не подключён"
        ctk.CTkLabel(
            calls_frame,
            text=status,
            font=("Segoe UI", 10),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        next_row = 1
        if not self._paired:
            ctk.CTkLabel(
                calls_frame,
                text=(
                    "1. calls.o2consult.ai → Настройки → Подключить ПК\n"
                    "2. Сгенерируйте код и вставьте ниже"
                ),
                font=("Segoe UI", 9),
                text_color=TEXT_SECONDARY,
                justify="left",
                anchor="w",
            ).grid(row=next_row, column=0, pady=(6, 4), sticky="w")
            next_row += 1

            ctk.CTkButton(
                calls_frame,
                text="Открыть Calls в браузере",
                command=self._open_calls_settings,
                height=28,
                fg_color=BG_CONTROL,
                hover_color=BG_CONTROL_HOVER,
                text_color=TEXT_PRIMARY,
            ).grid(row=next_row, column=0, pady=(0, 6), sticky="ew")
            next_row += 1

            self._pairing_code_var = ctk.StringVar()
            ctk.CTkEntry(
                calls_frame,
                textvariable=self._pairing_code_var,
                placeholder_text="v1.…",
                height=28,
                font=("Segoe UI", 10),
                fg_color=BG_INPUT,
            ).grid(row=next_row, column=0, pady=(0, 6), sticky="ew")
            next_row += 1

            self._pairing_error_label = ctk.CTkLabel(
                calls_frame,
                text="",
                font=("Segoe UI", 9),
                text_color="#f87171",
                anchor="w",
                justify="left",
            )
            self._pairing_error_label.grid(row=next_row, column=0, pady=(0, 4), sticky="w")
            next_row += 1

            ctk.CTkButton(
                calls_frame,
                text="Подключить",
                command=self._connect_calls,
                height=28,
                fg_color=ACCENT_PRIMARY,
                hover_color=ACCENT_PRIMARY_HOVER,
            ).grid(row=next_row, column=0, pady=(0, 4), sticky="ew")
            next_row += 1

        if self._paired and self._on_reset_pairing:
            ctk.CTkButton(
                calls_frame,
                text="Сбросить / переподключить",
                command=self._reset_pairing,
                height=28,
                fg_color=BG_CONTROL,
                hover_color=BG_CONTROL_HOVER,
                text_color=TEXT_PRIMARY,
            ).grid(row=next_row, column=0, pady=(6, 0), sticky="w")

        ctk.CTkButton(
            self, text="Save", command=self._save,
            fg_color=ACCENT_PRIMARY, hover_color=ACCENT_PRIMARY_HOVER,
        ).grid(row=1, column=0, pady=(0, PAD))

    def _pick_folder(self):
        path = filedialog.askdirectory(initialdir=self._path_var.get())
        if path:
            self._path_var.set(path)

    def _open_calls_settings(self):
        webbrowser.open("https://calls.o2consult.ai/settings")

    def _connect_calls(self):
        code = self._pairing_code_var.get().strip()
        if not code:
            self._pairing_error_label.configure(text="Вставьте код подключения")
            return
        try:
            self._cfg = apply_pairing_to_config(self._cfg, code)
        except PairingError as exc:
            self._pairing_error_label.configure(text=str(exc))
            return

        self._pairing_error_label.configure(text="")
        save_config(self._cfg)
        self._on_save(self._cfg)
        if self._on_pairing_complete:
            self._on_pairing_complete(self._cfg)
        self.destroy()

    def _reset_pairing(self):
        if self._on_reset_pairing:
            self._on_reset_pairing(reopen_settings=sys.platform == "darwin")
        self.destroy()

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
        self._cfg["start_with_windows"] = bool(self._autostart_var.get())
        save_config(self._cfg)
        if self._cfg["start_with_windows"]:
            autostart.enable(autostart.current_executable_path())
        else:
            autostart.disable()
        self._on_save(self._cfg)
        self.destroy()
