"""#713: move captions off a busy bottom band (score bug / HUD). Automatic only.

**Off by default behind `CAPTION_AUTO_PLACE`.** The detector counts unique chroma
in the bottom eighth versus the top, which is a proxy for "something is overlaid
there" -- and #717 already concedes chroma is not a face. Measured: a flat sky over
a textured lower half, the commonest b-roll composition, scores top=1 / bottom=87
and would relocate every caption to the top of the video with no HUD present at
all. This repo keeps uncertain visual features behind a default-off flag
(`SCENE_MATCHED_BROLL`, `LUFS_NORMALIZE`); this one joins them until #717 can tell
a score bug from a landscape. With the flag unset the burned ASS is unchanged.
"""

from __future__ import annotations

from core.logging import get_logger

logger = get_logger("video.caption_place")


def choose_caption_anchor(path: str | None) -> str:
    """'top' when the default bottom caption band is occupied, else 'bottom'."""
    if not path:
        return "bottom"
    from core.providers import flag_enabled

    if not flag_enabled("CAPTION_AUTO_PLACE"):
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
