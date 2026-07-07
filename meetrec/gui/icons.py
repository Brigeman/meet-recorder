import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from meetrec.gui.theme import STATE_COLORS
from meetrec.platform import app_icon_path as platform_app_icon_path

_DEFAULT_SIZE = 256
_ICON_CACHE: dict[int, Image.Image] = {}


def _resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        return base / "meetrec" / "resources"
    return Path(__file__).resolve().parents[1] / "resources"


def app_ico_path() -> str:
    resources = _resource_dir()
    path = platform_app_icon_path(str(resources))
    if os.path.isfile(path):
        return path
    fallback = resources / "logo.png"
    return str(fallback)


def load_logo_image(size: int = 64) -> Image.Image:
    if size in _ICON_CACHE:
        return _ICON_CACHE[size].copy()
    logo = Image.open(_resource_dir() / "logo.png").convert("RGBA")
    bbox = logo.getbbox()
    if bbox:
        logo = logo.crop(bbox)
    scaled = logo.resize((size, size), Image.LANCZOS)
    _ICON_CACHE[size] = scaled
    return scaled.copy()


def make_menu_bar_icon(state: str, size: int = 18) -> Image.Image:
    """High-contrast tray icon — the full logo is faint when shrunk to menu-bar size."""
    src = load_logo_image(size=max(size * 4, 64))
    rgba = src.convert("RGBA")
    # Flatten semi-transparent pixels so the shield stays visible on light/dark menu bars.
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 0))
    flattened = Image.alpha_composite(background, rgba)
    pixels = flattened.load()
    width, height = flattened.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            alpha = min(255, int(a * 1.35))
            pixels[x, y] = (r, g, b, alpha)
    icon = flattened.resize((size, size), Image.LANCZOS)
    if state == "recording":
        draw = ImageDraw.Draw(icon)
        dot = max(4, size // 4)
        pad = 1
        draw.ellipse(
            (size - dot - pad, size - dot - pad, size - pad, size - pad),
            fill=STATE_COLORS["recording"],
        )
    return icon


def make_tray_icon(state: str, size: int = 64) -> Image.Image:
    if size <= 22:
        return make_menu_bar_icon(state, size=size)
    img = load_logo_image(size=size)
    if state == "recording":
        draw = ImageDraw.Draw(img)
        dot = max(8, size // 4)
        pad = max(2, size // 24)
        x1 = size - dot - pad
        y1 = size - dot - pad
        x2 = size - pad
        y2 = size - pad
        draw.ellipse((x1, y1, x2, y2), fill=STATE_COLORS["recording"])
    return img


def make_icon(color_or_state, size=64):
    if isinstance(color_or_state, str) and color_or_state in STATE_COLORS:
        return make_tray_icon(color_or_state, size=size)
    state = "recording" if color_or_state == STATE_COLORS.get("recording") else "monitoring"
    return make_tray_icon(state, size=size)


def make_ico(_color=None):
    return app_ico_path()
