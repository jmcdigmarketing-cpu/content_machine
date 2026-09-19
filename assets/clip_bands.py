"""What each clip carries at the top and bottom of its own frame (#788).

Wave 23 cropped a fixed 18% off the bottom of every shot so GTA's mission text could not
reach the caption band. That is blunt in both directions: a 2K score bug or a Fortnite kill
feed sits at the *top* and survives, and a clean clip loses 18% of its picture for nothing.

This measures the clip once - at ingest, or lazily the first time it is used - and stores the
answer in the clip index beside `hud`:

    "bands": {"top": 0.0, "bottom": 0.14}

The reading is the luminance-step idea from #717 (`video/caption_place._row_luma`): a strip of
burned-in text or a HUD plate makes rows whose mean luma sits well away from the picture's,
and it holds still. Two frames are measured and a band counts only when both agree, which is
what keeps a bright sky, a passing car or a muzzle flash from costing a clip its picture.

`crop_for_clip` turns a stored reading into the (top, bottom) crop a shot uses. A measurement
only adds crop: `BACKGROUND_CROP_BOTTOM` stays the floor at the bottom, so a library that has
never been measured behaves exactly as it did in wave 23.

**What this does not see.** Measured across the real library (2026-09-19): full-width plates
are found, partial-width HUD graphics are not - a 2K score bug or a Fortnite kill feed covers
too little of a row to move that row's mean. Catching those is #717/#727's column-wise work,
which still misses 4 of 30 real score bars (#731). #788 stays open for it.
"""

from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger

logger = get_logger("assets.clip_bands")

# A band is read in rows this tall (as a share of frame height), up to _MAX_BAND.
_ROW = 0.02
_MAX_BAND = 0.22
# How far a row's mean luma must sit from the picture's median to read as a plate, and how
# close the two frames' readings must be to count as "the same thing is still there".
_MIN_STEP = 0.22
# A plate ends abruptly; a sky or a road fades. This is what keeps scenery out (#728's shape).
_MIN_EDGE_STEP = 0.25
_FRAME_FRACTIONS = (0.2, 0.6)
# Beyond this the zoom costs more picture than the HUD costs attention.
_MAX_TOTAL_CROP = 0.30


def _median(values: list[float]) -> float:
    from video.caption_place import _median as _caption_median

    return _caption_median(values)


def _row_means(image, y0: int, y1: int, rows: int) -> list[float]:
    """Mean luma of each of `rows` horizontal slices between y0 and y1."""
    from video.caption_place import _row_luma

    step = max(1, (y1 - y0) // max(1, rows))
    out: list[float] = []
    for y in range(y0, y1, step):
        sampled = _row_luma(image, y, min(y + step, y1))
        if sampled:
            out.append(sum(sampled) / len(sampled))
    return out


def _band_share(image, *, top: bool) -> float:
    """Share of the frame height at one edge that reads as burned-in text or a HUD plate.

    A plate ends in a *step*: one row is picture, the next is plate. A bright sky or a dark
    road has no such edge, only a gradient - that is what separates this from "the top of the
    frame is lighter than the middle", which is true of most outdoor footage.
    """
    width, height = image.size
    if width < 16 or height < 16:
        return 0.0
    row_px = max(2, int(height * _ROW))
    limit = max(row_px * 2, int(height * _MAX_BAND))
    middle = _row_means(image, int(height * 0.35), int(height * 0.65), 8)
    if not middle:
        return 0.0
    picture = _median(middle)
    reference = max(picture, 12.0)
    if top:
        rows = _row_means(image, 0, limit, limit // row_px)
    else:
        rows = list(reversed(_row_means(image, height - limit, height, limit // row_px)))
    if len(rows) < 3:
        return 0.0
    # The deepest row that still sits away from the picture, and the step that ends the band.
    depth = 0
    for i, value in enumerate(rows):
        if abs(value - picture) / reference < _MIN_STEP:
            break
        depth = i + 1
    if depth == 0 or depth >= len(rows):
        return 0.0
    step = abs(rows[depth] - rows[depth - 1]) / reference
    if step < _MIN_EDGE_STEP:
        return 0.0
    return round(depth * row_px / height, 3)


def bands_from_frames(frames: list[Any]) -> dict[str, float]:
    """{"top": share, "bottom": share} - the smaller reading of the frames, so one frame alone
    can never cost a clip its picture."""
    readings = [
        {"top": _band_share(f, top=True), "bottom": _band_share(f, top=False)} for f in frames
    ]
    if not readings:
        return {"top": 0.0, "bottom": 0.0}
    return {
        "top": round(min(r["top"] for r in readings), 3),
        "bottom": round(min(r["bottom"] for r in readings), 3),
    }


def measure_bands(path: str, *, duration: float | None = None) -> dict[str, float]:
    """Measure a clip's text bands. Never raises; an unreadable clip reads as no bands."""
    from core.hud_detect import _load_frame_at

    if duration is None:
        try:
            from assets.clip_ingest import _probe_duration

            duration = _probe_duration(path)
        except Exception as exc:
            logger.debug("bands duration probe skipped: %s", exc)
            duration = None
    span = float(duration or 0.0)
    frames = []
    for fraction in _FRAME_FRACTIONS:
        try:
            frame = _load_frame_at(path, span * fraction if span else 0.0)
        except Exception as exc:
            logger.debug("bands frame skipped (%s): %s", path, exc)
            frame = None
        if frame is not None:
            frames.append(frame)
    if len(frames) < 2:
        return {"top": 0.0, "bottom": 0.0}
    return bands_from_frames(frames)


def _index_clips() -> dict[str, Any]:
    try:
        from core.owned_beats import load_clip_index

        index = load_clip_index()
    except Exception as exc:
        logger.debug("clip index unreadable: %s", exc)
        return {}
    clips = index.get("clips") if isinstance(index, dict) else None
    return clips if isinstance(clips, dict) else {}


def stored_bands(path: str) -> dict[str, float] | None:
    """The clip's stored reading, or None when it has never been measured."""
    if not path:
        return None
    wanted = os.path.normcase(os.path.abspath(path))
    for key, meta in _index_clips().items():
        if os.path.normcase(os.path.abspath(str(key))) != wanted:
            continue
        bands = (meta or {}).get("bands")
        if isinstance(bands, dict):
            return {
                "top": float(bands.get("top") or 0.0),
                "bottom": float(bands.get("bottom") or 0.0),
            }
        return None
    return None


def crop_for_clip(path: str) -> tuple[float, float]:
    """(top, bottom) crop for this clip's shots, as shares of the source frame height.

    A measurement only ever *adds* crop. `BACKGROUND_CROP_BOTTOM` stays the floor at the
    bottom because the thing it was added for - GTA's mission subtitles, white text on no
    plate - is not a luminance step and is not measured here (#788 stays open for that).
    """
    from assets.fast_cut import crop_bottom

    floor = crop_bottom()
    bands = stored_bands(path)
    if bands is None:
        return 0.0, floor
    top = max(0.0, min(_MAX_BAND, bands.get("top", 0.0)))
    bottom = max(floor, min(_MAX_BAND, bands.get("bottom", 0.0)))
    total = top + bottom
    if total > _MAX_TOTAL_CROP and total > 0:
        scale = _MAX_TOTAL_CROP / total
        top, bottom = round(top * scale, 3), round(bottom * scale, 3)
    return top, bottom
