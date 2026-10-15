"""Local thumbnail plate: a short headline, a stroke, and a contrast gate.

Flux is asked for a picture with no words. This module paints the words
afterwards, and only when they stay readable against the pixels behind them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

MARGIN = 64
MIN_CONTRAST = 4.5
# #1178: how dark the plate behind the words is (0-1). 4 of 8 thumbnails had gone out with no
# words because one sampled pixel was too light for white text.
PLATE_DARKNESS = 0.72
_TEXT = (255, 255, 255)
_STROKE = (0, 0, 0)
_STROKE_PX = 3


@dataclass
class ThumbnailPlate:
    path: str
    words: list[str]
    width: int
    height: int
    margin: int
    text_box: tuple[int, int, int, int]
    contrast: float
    refused: str = ""
    backed: bool = False  # #1178: the words sit on a dark plate


def headline_words(title: str) -> list[str]:
    """Three to five words. A longer title keeps the first four."""
    words = [w for w in (title or "").split() if w]
    if len(words) > 5:
        return words[:4]
    return words


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """WCAG relative-luminance contrast of two sRGB colours."""

    def _lin(channel: int) -> float:
        c = channel / 255.0
        if c <= 0.04045:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    def _lum(rgb: tuple[int, int, int]) -> float:
        r, g, b = (_lin(v) for v in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    lighter = max(_lum(a), _lum(b))
    darker = min(_lum(a), _lum(b))
    return (lighter + 0.05) / (darker + 0.05)


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose_thumbnail(
    base: Image.Image,
    title: str,
    dest: str,
    *,
    subject: Image.Image | None = None,
    min_contrast: float = MIN_CONTRAST,
) -> ThumbnailPlate:
    """Paint the headline onto a copy of ``base`` and save it.

    A subject image is pasted only when the caller passes one. White (or any
    colour) whose contrast against the pixels behind the words is below
    ``min_contrast`` gets a dark plate behind it (#1178); only when even the plate
    cannot reach it is the overlay refused and nothing written.
    """
    img = base.convert("RGB").copy()
    width, height = img.size
    words = headline_words(title) or ["Video"]
    line = " ".join(words)
    sample = img.getpixel((max(MARGIN, width // 4), height // 2))
    rgb = tuple(sample[:3])
    ratio = contrast_ratio(_TEXT, rgb)
    empty = (0, 0, 0, 0)
    backed = False
    if ratio < min_contrast:
        keep = 1.0 - PLATE_DARKNESS
        behind = (int(rgb[0] * keep), int(rgb[1] * keep), int(rgb[2] * keep))
        backed_ratio = contrast_ratio(_TEXT, behind)
        if backed_ratio >= min_contrast:
            ratio, backed = backed_ratio, True
    if ratio < min_contrast:
        return ThumbnailPlate(
            path="",
            words=words,
            width=width,
            height=height,
            margin=MARGIN,
            text_box=empty,
            contrast=ratio,
            refused="contrast",
        )

    if subject is not None:
        cut = subject.convert("RGB")
        cut.thumbnail((max(1, width // 3), max(1, height - 2 * MARGIN)))
        x = width - MARGIN - cut.width
        y = max(MARGIN, (height - cut.height) // 2)
        img.paste(cut, (x, y))

    draw = ImageDraw.Draw(img)
    size = 72
    font = _font(size)
    while size > 28:
        bbox = draw.textbbox((0, 0), line, font=font)
        if bbox[2] - bbox[0] <= width - 2 * MARGIN - 2 * _STROKE_PX:
            break
        size -= 4
        font = _font(size)
    bbox = draw.textbbox((0, 0), line, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad = _STROKE_PX + 2
    x = MARGIN + pad
    y = max(MARGIN + pad, (height - th) // 2)
    if y + th + pad > height - MARGIN:
        y = max(MARGIN + pad, height - MARGIN - pad - th)
    if backed:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rectangle(
            (x - pad * 4, y - pad * 3, x + tw + pad * 4, y + th + pad * 4),
            fill=(0, 0, 0, int(255 * PLATE_DARKNESS)),
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
    # Shadow, then a dark stroke, then the fill. The stroke is what keeps a
    # light photo from swallowing the letters when the sampled pixel passed.
    draw.text((x + 3, y + 3), line, fill=(0, 0, 0), font=font)
    draw.text(
        (x, y),
        line,
        fill=_TEXT,
        font=font,
        stroke_width=_STROKE_PX,
        stroke_fill=_STROKE,
    )
    text_box = (x - pad, y - pad, x + tw + pad, y + th + pad)
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    img.save(dest, "JPEG", quality=92)
    return ThumbnailPlate(
        path=dest,
        words=words,
        width=width,
        height=height,
        margin=MARGIN,
        text_box=text_box,
        contrast=ratio,
        backed=backed,
    )
