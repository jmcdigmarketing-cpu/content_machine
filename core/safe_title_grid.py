"""#186: YouTube chrome / title-safe rects for the player and studio still."""

from __future__ import annotations


def safe_title_rects(width: int, height: int) -> dict[str, tuple[int, int, int, int]]:
    """x0, y0, x1, y1. Bottom 20% is YouTube chrome; title-safe sits above it."""
    w = max(1, int(width))
    h = max(1, int(height))
    chrome_y = int(h * 0.8)
    inset_x = int(w * 0.1)
    inset_y = int(h * 0.1)
    return {
        "chrome": (0, chrome_y, w, h),
        "title_safe": (inset_x, inset_y, w - inset_x, chrome_y),
    }
