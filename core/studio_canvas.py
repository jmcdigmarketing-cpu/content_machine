"""#152 mechanical slice: last thumb + inspect_thumbnail overlay. No drag."""

from __future__ import annotations

from typing import Any

from core.safe_title_grid import safe_title_rects
from core.thumbnail_safe_area import inspect_thumbnail


def studio_overlay_for(thumb_path: str) -> dict[str, Any]:
    check = inspect_thumbnail(thumb_path)
    from PIL import Image

    with Image.open(thumb_path) as image:
        width, height = image.size
    return {
        "path": check.path,
        "bottom_quiet": check.bottom_quiet,
        "detail": check.detail,
        "rects": safe_title_rects(width, height),
    }
