"""#713 / #717: move captions off an occupied bottom band. Automatic only.

**Still gated behind `CAPTION_AUTO_PLACE` (#718), default off.**

#713 anchored by unique chroma in the bottom band versus the top, which is why a
flat sky over textured ground read as a HUD: measured top=1 / bottom=87 on the
commonest b-roll composition, with nothing overlaid at all. Busy-ness is not the
signal, and chroma cannot see the dark lower-third #717 named.

**#717: the signal is a step in per-row brightness.** An overlay -- a score bug, a
lower-third, a watermark -- is composited on top, so it introduces a horizontal
band whose mean luminance differs sharply from the footage above and below it.
Scenery does not: it varies smoothly. Two conditions, both required:

* **contrast** -- the spread of per-row mean luma across the band, relative to its
  median, clears `_MIN_SPREAD`;
* **a step** -- one row-to-row jump accounts for at least `_MIN_STEP_SHARE` of that
  spread. A composited edge is abrupt; a sunset gradient spreads the same total
  change over every row and fails this.

Measured on the fixtures in `tests/test_wave8.py` (spread/median, step share):
sky over grass 0.09 / 0.75 and sky over city 0.13 / 0.92 -- both rejected on
spread; a bright score bug 1.11 / 1.00, a flat dark lower-third 1.02 / 0.93 and a
band-filling overlay 1.07 / 0.82 -- all caught. A strong in-band gradient clears
spread and is rejected on step. So the spread gate rejects scenery and the step
gate rejects gradients; both carry weight, and chroma is not consulted at all.

Deliberately no face detection: a face is not an overlay, and moving a caption off
someone's chin is a different item.
"""

from __future__ import annotations

from core.logging import get_logger

logger = get_logger("video.caption_place")

# Per-row mean-luma spread, relative to the band median. Scenery measured 0.09.
_MIN_SPREAD = 0.35
# Share of that spread carried by a single row-to-row jump. A composited edge is
# ~1.0; a smooth gradient over N rows is ~1/N.
_MIN_STEP_SHARE = 0.5
# Fewer rows than this and "per-row" means nothing.
_MIN_ROWS = 8
# A band that is almost black end to end has no usable contrast ratio.
_MIN_MEDIAN_LUMA = 4.0
# Rows sampled, as a multiple of the caption band. An overlay that fills the band
# edge-to-edge has no step *inside* it -- its edge is just above. Measured
# (spread/median at window x1/x2/x3): a band-filling overlay reads 0.24/0.23/1.07,
# so x1 and x2 miss it; sky-over-grass stays 0.09/0.08/0.09 and sky-over-city
# 0.13/0.12/0.13, so x3 costs nothing there. x4 reaches half way up the frame,
# where a real horizon starts to land inside the window.
_WINDOW_BANDS = 3


def _row_luma(rgb, y0: int, y1: int) -> list[float]:
    """Mean luminance per sampled row of the band."""
    width, _height = rgb.size
    step_x = max(1, width // 64)
    step_y = max(1, (y1 - y0) // 32 or 1)
    rows: list[float] = []
    for y in range(y0, y1, step_y):
        total = 0.0
        count = 0
        for x in range(0, width, step_x):
            r, g, b = rgb.getpixel((x, y))[:3]
            total += 0.299 * r + 0.587 * g + 0.114 * b
            count += 1
        if count:
            rows.append(total / count)
    return rows


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def band_reading(path: str | None) -> tuple[str, tuple[float, float] | None]:
    """(state, metrics). State is 'ok', 'no_frame' or 'no_contrast'.

    The three are different answers and were worth separating: a path that yields
    no frame is a usage error, while a band that is flat or pure black is a
    *measured* result whose operational meaning is "captions stay at the bottom".
    Collapsing them made `ops caption-anchor` report the one real committed clip --
    whose first frame has a black bottom band, median luma 0.00 -- as if the file
    were broken.
    """
    if not path:
        return "no_frame", None
    try:
        from core.hud_detect import _load_frame
    except Exception as exc:
        logger.debug("caption-place imports skipped: %s", exc)
        return "no_frame", None
    image = _load_frame(path)
    if image is None:
        return "no_frame", None
    rgb = image.convert("RGB")
    width, height = rgb.size
    if height < 16 or width < 16:
        return "no_frame", None
    band = max(8, height // 8)
    window = min(height, band * _WINDOW_BANDS)
    rows = _row_luma(rgb, height - window, height)
    if len(rows) < _MIN_ROWS:
        return "no_frame", None
    median = _median(rows)
    if median < _MIN_MEDIAN_LUMA:
        return "no_contrast", None
    spread = max(rows) - min(rows)
    if spread <= 0:
        return "ok", (0.0, 0.0)
    biggest_jump = max(abs(rows[i + 1] - rows[i]) for i in range(len(rows) - 1))
    return "ok", (spread / median, biggest_jump / spread)


def band_overlay_metrics(path: str | None) -> tuple[float, float] | None:
    """(spread/median, step share) for the bottom band, or None when unmeasurable.

    Public so the numbers can be measured directly rather than inferred from a
    boolean -- the thresholds above were set from real readings, not taste.
    """
    return band_reading(path)[1]


def bottom_band_overlay(path: str | None) -> bool:
    """True when the bottom caption band carries a composited overlay.

    Independent of the flag so it can be measured directly; `choose_caption_anchor`
    is what respects `CAPTION_AUTO_PLACE`.
    """
    metrics = band_overlay_metrics(path)
    if metrics is None:
        return False
    spread_ratio, step_share = metrics
    return spread_ratio >= _MIN_SPREAD and step_share >= _MIN_STEP_SHARE


def choose_caption_anchor(path: str | None) -> str:
    """'top' when the default bottom caption band is occupied, else 'bottom'."""
    if not path:
        return "bottom"
    from core.providers import flag_enabled

    if not flag_enabled("CAPTION_AUTO_PLACE"):
        return "bottom"
    try:
        return "top" if bottom_band_overlay(path) else "bottom"
    except Exception as exc:
        logger.debug("caption placement skipped: %s", exc)
        return "bottom"
