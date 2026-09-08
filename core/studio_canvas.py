"""#152 mechanical slice: last thumb + inspect_thumbnail overlay. Drag snaps to title-safe."""

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


def clamp_layer_into_title_safe(
    x: int,
    y: int,
    width: int,
    height: int,
    title_safe: tuple[int, int, int, int],
) -> tuple[int, int]:
    x0, y0, x1, y1 = (int(v) for v in title_safe)
    w = max(1, int(width))
    h = max(1, int(height))
    max_x = max(x0, x1 - w)
    max_y = max(y0, y1 - h)
    nx = min(max(int(x), x0), max_x)
    ny = min(max(int(y), y0), max_y)
    return nx, ny
