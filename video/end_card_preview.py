"""#187. Preview the last-second end card before a full render."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.caption_contrast import parse_hex
from core.font_cache import load_font
from video.channel_outro import TARGET_H, TARGET_W, end_card_text_y, resolve_end_card


def preview_text_xy(text_w: int, text_h: int, bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    x = (TARGET_W - text_w) // 2 - bbox[0]
    y = end_card_text_y(text_h) - bbox[1]
    return x, y


@dataclass(frozen=True)
class EndCardPreview:
    path: str
    text: str


def _card_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return load_font("arialbd.ttf", 64)


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
    text_w = int(bbox[2] - bbox[0])
    text_h = int(bbox[3] - bbox[1])
    x, y = preview_text_xy(
        text_w,
        text_h,
        (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
    )
    draw.text((x, y), text, font=font, fill=fg)
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest)
    return EndCardPreview(path=str(dest), text=text)
