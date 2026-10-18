"""#185 / #297. Caption-fill vs sampled background contrast (WCAG-ish ratio).

Advisory only — does not enter the report card, so GRADE_VERSION stays put.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageStat

from core.logging import get_logger

logger = get_logger("core.caption_contrast")

# WCAG AA for normal text. Captions are large, but the burned fill is small
# on a phone, so we keep the stricter 4.5:1 rather than large-text 3:1.
AA_RATIO = 4.5
CAPTION_BAND = 0.20


@dataclass(frozen=True)
class CaptionContrastCheck:
    ratio: float
    passed: bool
    fill_hex: str
    band_rgb: tuple[int, int, int]
    detail: str
    path: str = ""


def _srgb_to_linear(channel: float) -> float:
    c = channel / 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


SCRIM_MAX = 0.45


def _graded(rgb: tuple[int, int, int], grade: dict[str, float] | None) -> tuple[int, int, int]:
    """The band after the channel's `eq` grade (contrast about mid-grey, then brightness)."""
    if not grade:
        return rgb
    contrast = float(grade.get("contrast", 1.0))
    brightness = float(grade.get("brightness", 0.0))
    out = [round(((v / 255.0 - 0.5) * contrast + 0.5 + brightness) * 255) for v in rgb]
    r, g, b = (max(0, min(255, v)) for v in out)
    return r, g, b


def scrim_alpha(
    fill: tuple[int, int, int],
    bands: list[tuple[int, int, int]],
    *,
    grade: dict[str, float] | None = None,
    target: float = AA_RATIO,
    cap: float = SCRIM_MAX,
) -> float:
    """#1268: how dark a black band behind the captions must be (0-``cap``) for the lightest
    sampled background band to reach ``target`` against the caption fill. 0 when every band
    already passes. Run 157's band, rgb(136,130,131) under white, read 3.8:1."""
    if not bands:
        return 0.0
    lightest = max((_graded(tuple(b), grade) for b in bands), key=relative_luminance)  # type: ignore[arg-type]
    if contrast_ratio(fill, lightest) >= target:
        return 0.0
    for step in range(1, round(cap * 100) + 1):
        alpha = step / 100.0
        r, g, b = (round(v * (1.0 - alpha)) for v in lightest)
        if contrast_ratio(fill, (r, g, b)) >= target:
            return alpha
    return cap


def parse_hex(value: str, default: str = "#FFFFFF") -> tuple[int, int, int]:
    raw = (value or default).strip().lstrip("#")
    if len(raw) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in raw):
        raw = default.lstrip("#")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def fill_hex_for_channel(channel_id: str | None) -> str:
    try:
        from config.channels import get_channel_profile

        skin = get_channel_profile(channel_id or "default").caption_skin or {}
        fill = str(skin.get("fill_color") or "").strip()
        if fill:
            return fill
    except Exception as exc:
        logger.debug("caption fill lookup skipped: %s", exc)
    try:
        from core.design_tokens import caption_fill_hex

        return caption_fill_hex(channel_id)
    except Exception as exc:
        logger.debug("caption fill tokens skipped: %s", exc)
    return "#FFFFFF"


def inspect_caption_band(
    path: str | Path,
    *,
    fill_hex: str = "#FFFFFF",
    band: float = CAPTION_BAND,
) -> CaptionContrastCheck:
    source = str(path)
    fill = parse_hex(fill_hex)
    with Image.open(source) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        y0 = max(0, int(height * (1.0 - float(band))))
        crop = rgb.crop((0, y0, width, height))
        stats = ImageStat.Stat(crop)
        band_rgb = (
            round(stats.mean[0]),
            round(stats.mean[1]),
            round(stats.mean[2]),
        )
    ratio = round(contrast_ratio(fill, band_rgb), 2)
    passed = ratio >= AA_RATIO
    detail = f"caption fill {fill_hex} vs band rgb{band_rgb} is {ratio:.1f}:1" + (
        "" if passed else f" (below {AA_RATIO}:1)"
    )
    return CaptionContrastCheck(
        ratio=ratio,
        passed=passed,
        fill_hex=fill_hex,
        band_rgb=band_rgb,
        detail=detail,
        path=source,
    )


def render_check(check: CaptionContrastCheck) -> str:
    status = "PASS" if check.passed else "REVIEW"
    return f"Caption contrast ADVISORY: {status} - {check.ratio:.1f}:1 - {check.detail}"
