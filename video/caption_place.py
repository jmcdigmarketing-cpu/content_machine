"""#713: move captions off a busy bottom band (score bug / HUD). Automatic only."""

from __future__ import annotations

from core.logging import get_logger

logger = get_logger("video.caption_place")


def choose_caption_anchor(path: str | None) -> str:
    """'top' when the default bottom caption band is occupied, else 'bottom'."""
    if not path:
        return "bottom"
    try:
        from core.hud_detect import _load_frame, _unique_chroma
    except Exception as exc:
        logger.debug("caption-place imports skipped: %s", exc)
        return "bottom"
    image = _load_frame(path)
    if image is None:
        return "bottom"
    rgb = image.convert("RGB")
    _width, height = rgb.size
    if height < 8:
        return "bottom"
    band = max(2, height // 8)
    top = _unique_chroma(rgb, 0, band)
    bottom = _unique_chroma(rgb, height - band, height)
    if bottom >= 12 and bottom > top * 1.5:
        return "top"
    return "bottom"
