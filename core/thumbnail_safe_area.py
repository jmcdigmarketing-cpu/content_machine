"""Pillow-only thumbnail check for YouTube's bottom chrome-safe area.

This is intentionally a conservative visual-density check, not face/text
recognition: high-contrast detail in the bottom 20% is flagged for human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat


@dataclass(frozen=True)
class ThumbnailSafeAreaCheck:
    path: str
    bottom_quiet: bool
    bottom_detail: float
    threshold: float = 18.0
    detail: str = ""


def inspect_thumbnail(path: str | Path) -> ThumbnailSafeAreaCheck:
    source = str(path)
    with Image.open(source) as image:
        gray = image.convert("L")
        width, height = gray.size
        bottom = gray.crop((0, int(height * 0.8), width, height))
        edges = bottom.filter(ImageFilter.FIND_EDGES)
        detail = float(ImageStat.Stat(edges).mean[0])
    bottom_quiet = detail < 18.0
    message = (
        "bottom 20% is visually quiet"
        if bottom_quiet
        else "bottom 20% has high-contrast detail; check title text/faces against YouTube chrome"
    )
    return ThumbnailSafeAreaCheck(source, bottom_quiet, round(detail, 2), detail=message)


def render_check(check: ThumbnailSafeAreaCheck) -> str:
    status = "QUIET" if check.bottom_quiet else "REVIEW"
    return (
        f"Thumbnail bottom-area HEURISTIC: {status} - {check.detail} "
        f"(edge detail {check.bottom_detail:.1f}; not OCR/face detection)"
    )
