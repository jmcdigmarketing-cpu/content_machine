"""#182. Overlay captions on a still frame so names can be proofread before burn."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.caption_contrast import parse_hex
from video.subtitles import split_script_into_lines


@dataclass(frozen=True)
class CaptionOverlayResult:
    path: str
    lines: list[str]


def _fill_rgb(channel_id: str | None) -> tuple[int, int, int]:
    from core.caption_contrast import fill_hex_for_channel

    return parse_hex(fill_hex_for_channel(channel_id))


def overlay_captions_on_still(
    frame_path: str,
    script: str,
    dest_path: str,
    *,
    channel_id: str | None = None,
) -> CaptionOverlayResult:
    """Draw the script's caption lines onto a copy of `frame_path`. No ffmpeg."""
    lines = [ln for ln in split_script_into_lines(script or "") if ln]
    if not lines:
        raise ValueError("script produced no caption lines")
    image = Image.open(frame_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    font_size = max(18, height // 22)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    fill = _fill_rgb(channel_id)
    stroke = (17, 17, 17)
    shown = lines[:2]
    y = int(height * 0.82)
    for line in shown:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=2)
        text_w = bbox[2] - bbox[0]
        x = max(8, (width - text_w) // 2)
        draw.text(
            (x, y),
            line,
            font=font,
            fill=fill,
            stroke_width=2,
            stroke_fill=stroke,
        )
        y += font_size + 8
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    image.save(dest_path)
    return CaptionOverlayResult(path=str(dest_path), lines=lines)
