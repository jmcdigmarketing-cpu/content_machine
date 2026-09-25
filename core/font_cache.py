"""#612. Cache Pillow font objects across thumbnail / overlay / end-card draws."""

from __future__ import annotations

import os
from functools import lru_cache

from PIL import ImageFont


@lru_cache(maxsize=32)
def load_font(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [path]
    windir = os.environ.get("WINDIR", r"C:\Windows")
    name = os.path.basename(path)
    candidates.append(os.path.join(windir, "Fonts", name))
    candidates.append("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return ImageFont.truetype(candidate, int(size))
        except OSError:
            continue
    return ImageFont.load_default()
