"""Generate logo.png and winrec.ico from source logo.jpg."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SRC_LOGO = ROOT / "logo.jpg"
OUT_DIR = ROOT / "winrec" / "resources"
OUT_PNG = OUT_DIR / "logo.png"
OUT_ICO = OUT_DIR / "winrec.ico"


def _make_transparent(img: Image.Image, tolerance: int = 12) -> Image.Image:
    rgba = img.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if r >= 255 - tolerance and g >= 255 - tolerance and b >= 255 - tolerance:
                pixels[x, y] = (255, 255, 255, 0)
    return rgba


def build_assets() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not SRC_LOGO.exists():
        raise FileNotFoundError(f"Source logo not found: {SRC_LOGO}")
    logo = Image.open(SRC_LOGO)
    transparent = _make_transparent(logo)
    transparent.save(OUT_PNG, format="PNG")

    sizes = [16, 20, 24, 32, 40, 48, 64, 256]
    base = transparent.copy()
    icons = [base.resize((size, size), Image.LANCZOS) for size in sizes]
    icons[0].save(
        OUT_ICO,
        format="ICO",
        append_images=icons[1:],
        sizes=[(size, size) for size in sizes],
    )


if __name__ == "__main__":
    build_assets()
