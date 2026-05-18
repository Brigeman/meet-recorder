"""App icon loading helpers for meeting prompt."""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
from PIL import Image

_APP_TO_ICON = {
    "microsoft teams": "teams",
    "zoom": "zoom",
    "slack": "slack",
    "discord": "discord",
    "google meet": "meet",
    "google chrome": "chrome",
    "microsoft edge": "edge",
    "whatsapp": "whatsapp",
    "telegram": "telegram",
}

_ICON_CACHE: dict[str, ctk.CTkImage] = {}
_ICON_DIR = Path(__file__).resolve().parents[1] / "resources" / "icons"


def icon_for_app(app_name: str, size: int = 40) -> ctk.CTkImage:
    key = _APP_TO_ICON.get((app_name or "").strip().lower(), "generic")
    cache_key = f"{key}:{size}"
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    path = _ICON_DIR / f"{key}.png"
    if not path.exists():
        path = _ICON_DIR / "generic.png"
    image = Image.open(path)
    icon = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
    _ICON_CACHE[cache_key] = icon
    return icon
