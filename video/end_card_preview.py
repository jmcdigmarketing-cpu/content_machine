"""#187. Preview the last-second end card before a full render."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.caption_contrast import parse_hex
from video.channel_outro import TARGET_H, TARGET_W, resolve_end_card


@dataclass(frozen=True)
class EndCardPreview:
    path: str
    text: str


def _card_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arialbd.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, 64)
            except OSError:
                continue
    return ImageFont.load_default()


def render_end_card_preview(dest_path: str, *, channel_id: str | None = None) -> EndCardPreview:
    card = resolve_end_card(channel_id)
    if not card:
        raise ValueError("end card is disabled or invalid for this channel")
    text = str(card["text"])
    bg = parse_hex(str(card["bg"]))
    fg = parse_hex(str(card["fg"]))
    image = Image.new("RGB", (TARGET_W, TARGET_H), bg)
    draw = ImageDraw.Draw(image)
    font = _card_font()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (TARGET_W - text_w) // 2 - bbox[0]
    y = (TARGET_H - text_h) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fg)
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest)
    return EndCardPreview(path=str(dest), text=text)
