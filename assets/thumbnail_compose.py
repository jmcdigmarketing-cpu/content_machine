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
    line_sizes: tuple[int, ...] = ()
    fill: tuple[int, int, int] = _TEXT


def headline_words(title: str) -> list[str]:
    """The title's first phrase, at most five words (#1183).

    The first four words gave "Topuria's Outlook: Can He". A title that breaks within its first
    five words (a colon, semicolon, comma or dash) keeps what comes before the break; otherwise
    five words, never ending on a small word ("Ben Affleck Gets Destroyed by" -> "... Destroyed").
    """
    from apis.topic_tokens import FUNCTION_WORDS

    words = [w for w in (title or "").split() if w]
    if len(words) <= 5:
        return words
    for i, word in enumerate(words[:5]):
        dash_next = i + 1 < len(words) and words[i + 1] in ("-", "\u2013", "\u2014")
        if i >= 1 and (word[-1] in ":;," or dash_next):
            return [*words[:i], word.rstrip(":;,")]
    head = _whole_names(words, 5, grow=2)
    while len(head) > 3 and head[-1].lower().strip(".,!?'") in FUNCTION_WORDS:
        head.pop()
    return head


def _whole_names(words: list[str], n: int, *, grow: int) -> list[str]:
    """#1483: the first `n` words, never ending inside a team's name - "Why are the New York"
    runs on to "Jets" when that adds `grow` words or fewer, else stops before the name."""
    from apis.team_gazetteer import team_spans

    for start, end in team_spans(words):
        if start < n < end:
            return words[:end] if end - n <= grow else words[:start] or words[:n]
    return words[:n]


def short_headline(words: list[str], n: int = 3) -> list[str]:
    """#1483: the short arm's `n` words. "Why the New" broke the New England Patriots; a cut
    inside a team's name gives the name itself ("New England Patriots") when it fits in n + 1."""
    from apis.team_gazetteer import team_spans

    for start, end in team_spans(words):
        if start < n < end:
            return words[start:end] if end - start <= n + 1 else words[:start] or words[:n]
    return words[:n]


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


def _hex_rgb(value: str) -> tuple[int, int, int] | None:
    raw = (value or "").strip().lstrip("#")
    if len(raw) != 6:
        return None
    try:
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    except ValueError:
        return None


def _channel_ink(channel_id: str | None, sample: tuple[int, int, int]) -> tuple[int, int, int]:
    """The channel's caption fill when it clears 4.5 against the sampled pixel."""
    if not channel_id:
        return _TEXT
    try:
        from config.channels import get_channel_profile

        skin = get_channel_profile(channel_id).caption_skin or {}
        fill = _hex_rgb(str(skin.get("fill_color") or ""))
    except Exception:
        return _TEXT
    if fill and contrast_ratio(fill, sample) >= MIN_CONTRAST:
        return fill
    return _TEXT


def _fit_lines(
    draw: ImageDraw.ImageDraw, words: list[str], width: int, height: int
) -> list[tuple[str, int]]:
    """One line when it fits. Otherwise two, the first larger, shrunk until both fit."""
    pad = _STROKE_PX + 2
    max_w = width - 2 * MARGIN - 2 * pad
    max_h = height - 2 * MARGIN - 2 * pad
    if max_w < 8 or not words:
        return [(" ".join(words) or "Video", 28)]
    for size in range(72, 11, -4):
        second = max(8, size - 8)
        font = _font(size)
        line = " ".join(words)
        box = draw.textbbox((0, 0), line, font=font)
        if box[2] - box[0] <= max_w and box[3] - box[1] <= max_h:
            return [(line, size)]
        if len(words) < 2:
            continue
        for cut in range(1, len(words)):
            first, rest = " ".join(words[:cut]), " ".join(words[cut:])
            top = draw.textbbox((0, 0), first, font=_font(size))
            bottom = draw.textbbox((0, 0), rest, font=_font(second))
            tw = max(top[2] - top[0], bottom[2] - bottom[0])
            th = (top[3] - top[1]) + 6 + (bottom[3] - bottom[1])
            if tw <= max_w and th <= max_h and size > second:
                return [(first, size), (rest, second)]
    return [(" ".join(words), 28)]


def compose_thumbnail(
    base: Image.Image,
    title: str,
    dest: str,
    *,
    subject: Image.Image | None = None,
    min_contrast: float = MIN_CONTRAST,
    channel_id: str | None = None,
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
    sample = img.getpixel((max(MARGIN, width // 4), height // 2))
    pixel = sample if isinstance(sample, tuple) else (sample, sample, sample)
    rgb = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
    ink = _channel_ink(channel_id, rgb)
    ratio = contrast_ratio(ink, rgb)
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
            fill=ink,
        )

    if subject is not None:
        cut = subject.convert("RGB")
        sw, sh = cut.size
        # #508: a tall portrait keeps its upper focal area (face), not the lower half.
        if sh > sw * 1.15:
            crop_h = min(sh, max(sw, round(sh * 0.42)))
            cut = cut.crop((0, 0, sw, max(1, crop_h)))
        cut.thumbnail((max(1, width // 3), max(1, height - 2 * MARGIN)))
        x = width - MARGIN - cut.width
        y = max(MARGIN, (height - cut.height) // 2)
        img.paste(cut, (x, y))

    draw = ImageDraw.Draw(img)
    fitted = _fit_lines(draw, words, width, height)
    fonts = [_font(size) for _text, size in fitted]
    boxes = [
        draw.textbbox((0, 0), text, font=font)
        for (text, _size), font in zip(fitted, fonts, strict=True)
    ]
    tw = max(int(box[2] - box[0]) for box in boxes)
    gap = 6 if len(fitted) > 1 else 0
    th = sum(int(box[3] - box[1]) for box in boxes) + gap
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
    cursor = y
    for (text, _size), font, box in zip(fitted, fonts, boxes, strict=True):
        draw.text((x + 3, cursor + 3), text, fill=(0, 0, 0), font=font)
        draw.text(
            (x, cursor),
            text,
            fill=ink,
            font=font,
            stroke_width=_STROKE_PX,
            stroke_fill=_STROKE,
        )
        cursor += int(box[3] - box[1]) + gap
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
        line_sizes=tuple(size for _text, size in fitted),
        fill=ink,
    )
