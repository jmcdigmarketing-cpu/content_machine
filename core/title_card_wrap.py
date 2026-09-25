"""#249: 2-line vs 3-line title-card wrap. Writes a still, not channels.json."""

from __future__ import annotations

import os
import textwrap


def wrap_title_card(text: str, *, max_lines: int = 2, width: int = 18) -> list[str]:
    lines = textwrap.wrap((text or "").strip(), width=max(4, int(width))) or [""]
    return lines[: max(1, int(max_lines))]


def write_title_card_still(text: str, dest: str, *, max_lines: int = 2) -> str:
    from PIL import Image, ImageDraw

    lines = wrap_title_card(text, max_lines=max_lines)
    image = Image.new("RGB", (1080, 608), (12, 16, 22))
    draw = ImageDraw.Draw(image)
    y = 220
    for line in lines:
        draw.text((80, y), line, fill=(255, 255, 255))
        y += 64
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    image.save(dest)
    return dest
