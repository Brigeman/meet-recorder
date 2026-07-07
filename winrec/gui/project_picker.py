"""Per-recording project selection dialog."""

from __future__ import annotations

import customtkinter as ctk

from winrec.calls.projects import default_project_id, list_known_projects
from winrec.gui.theme import (
    ACCENT_PRIMARY,
    ACCENT_PRIMARY_HOVER,
    BG_CARD,
    BG_DARK,
    BG_INPUT,
    PAD,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class ProjectPickerDialog(ctk.CTkToplevel):
    """Choose project before starting a recording."""

    def __init__(self, master, config: dict, on_confirm, on_cancel=None):
        super().__init__(master)
        self._cfg = dict(config)
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._result: str | None = None

        self.title("Проект для записи")
        self.geometry("420x280")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        card.grid(row=0, column=0, padx=PAD, pady=PAD, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Куда отправить эту запись?",
            font=("Segoe UI", 13, "bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        ctk.CTkLabel(
            card,
            text="Можно сменить позже в веб-кабинете Calls.",
            font=("Segoe UI", 10),
            text_color=TEXT_SECONDARY,
            justify="left",
        ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        projects = list_known_projects(self._cfg)
        options = [("— Без проекта —", "")]
        for item in projects:
            options.append((item["name"], item["id"]))

        self._project_var = ctk.StringVar(value=default_project_id(self._cfg) or "")
        labels = [label for label, _ in options]
        values = [value for _, value in options]

        def _map_label_to_value(label: str) -> str:
            for opt_label, opt_value in options:
                if opt_label == label:
                    return opt_value
            return ""

        current = self._project_var.get()
        current_label = labels[0]
        for opt_label, opt_value in options:
            if opt_value == current:
                current_label = opt_label
                break

        self._option_menu = ctk.CTkOptionMenu(
            card,
            values=labels,
            command=lambda label: self._project_var.set(_map_label_to_value(label)),
            width=320,
            height=32,
            fg_color=BG_INPUT,
        )
        self._option_menu.set(current_label)
        self._option_menu.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="ew")
        buttons.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            buttons,
            text="Отмена",
            command=self._cancel,
            fg_color=BG_INPUT,
            hover_color=ACCENT_PRIMARY_HOVER,
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            buttons,
            text="Записать",
            command=self._confirm,
            fg_color=ACCENT_PRIMARY,
            hover_color=ACCENT_PRIMARY_HOVER,
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def _confirm(self):
        label = self._option_menu.get()
        for opt_label, opt_value in [
            ("— Без проекта —", ""),
            *[(item["name"], item["id"]) for item in list_known_projects(self._cfg)],
        ]:
            if opt_label == label:
                self._result = opt_value or None
                break
        else:
            self._result = self._project_var.get() or None
        self._on_confirm(self._result)
        self.destroy()

    def _cancel(self):
        if self._on_cancel:
            self._on_cancel()
        self.destroy()
