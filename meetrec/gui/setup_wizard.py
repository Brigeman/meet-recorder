"""First-run setup wizard for Calls pairing."""

import customtkinter as ctk
import webbrowser

from meetrec.calls.pairing import PairingError, apply_pairing_to_config
from meetrec.config import save_config
from meetrec.gui.theme import (
    ACCENT_PRIMARY,
    ACCENT_PRIMARY_HOVER,
    BG_CARD,
    BG_DARK,
    BG_INPUT,
    PAD,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SetupWizard(ctk.CTkToplevel):
    def __init__(self, master, config: dict, on_complete):
        super().__init__(master)
        self._cfg = dict(config)
        self._on_complete = on_complete
        self._completed = False

        self.title("Подключение к Calls")
        self.geometry("480x360")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._skip)

        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        card.grid(row=0, column=0, padx=PAD, pady=PAD, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Подключите запись к Calls",
            font=("Segoe UI", 14, "bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        ctk.CTkLabel(
            card,
            text=(
                "1. Откройте calls.o2consult.ai (нужен VPN)\n"
                "2. Настройки → Подключить ПК\n"
                "3. Сгенерируйте код и вставьте его ниже"
            ),
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY,
            justify="left",
        ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkButton(
            card,
            text="Открыть Calls в браузере",
            command=self._open_calls,
            fg_color=BG_INPUT,
            hover_color=ACCENT_PRIMARY_HOVER,
            text_color=TEXT_PRIMARY,
        ).grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")

        self._code_var = ctk.StringVar()
        ctk.CTkEntry(
            card,
            textvariable=self._code_var,
            placeholder_text="v1.…",
            height=32,
            font=("Segoe UI", 11),
            fg_color=BG_INPUT,
        ).grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")

        self._error_label = ctk.CTkLabel(
            card, text="", font=("Segoe UI", 10), text_color="#f87171"
        )
        self._error_label.grid(row=4, column=0, padx=16, pady=(0, 8), sticky="w")

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=5, column=0, padx=16, pady=(4, 16), sticky="ew")
        buttons.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            buttons,
            text="Пропустить",
            command=self._skip,
            fg_color=BG_INPUT,
            hover_color=ACCENT_PRIMARY_HOVER,
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            buttons,
            text="Готово",
            command=self._submit,
            fg_color=ACCENT_PRIMARY,
            hover_color=ACCENT_PRIMARY_HOVER,
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def _open_calls(self):
        webbrowser.open("https://calls.o2consult.ai/settings")

    def _submit(self):
        code = self._code_var.get().strip()
        if not code:
            self._error_label.configure(text="Вставьте код подключения")
            return
        try:
            self._cfg = apply_pairing_to_config(self._cfg, code)
        except PairingError as exc:
            self._error_label.configure(text=str(exc))
            return

        save_config(self._cfg)
        self._completed = True
        self._on_complete(self._cfg)
        self.destroy()

    def _skip(self):
        self._cfg["calls_setup_skipped"] = True
        save_config(self._cfg)
        self._on_complete(self._cfg)
        self.destroy()

    @property
    def completed(self) -> bool:
        return self._completed
