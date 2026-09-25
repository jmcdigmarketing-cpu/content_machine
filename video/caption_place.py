"""#713 / #717 / #721: move captions off an occupied bottom band. Automatic only.

**Opt-in (`CAPTION_AUTO_PLACE=true`).** On by default from #721 until #727
(2026-09-13): measured on 50 real Pexels stock clips with no overlay, it moved
captions on 2. Inconclusive never moves a caption: a still image, a locked-off shot
or a clip under a second has no motion to compare against and stays at the bottom.

#713 anchored by unique chroma in the bottom band versus the top, which is why a
flat sky over textured ground read as a HUD: measured top=1 / bottom=87 on the
commonest b-roll composition, with nothing overlaid at all. Busy-ness is not the
signal, and chroma cannot see the dark lower-third #717 named.

**#717: the spatial signal is a step in per-row brightness.** An overlay -- a score
bug, a lower-third, a watermark -- is composited on top, so it introduces a
horizontal band whose mean luminance differs sharply from the footage above and
below it. Scenery mostly does not: it varies smoothly. Two conditions, both
required:

* **contrast** -- the spread of per-row mean luma across the band, relative to its
  median, clears `_MIN_SPREAD`;
* **a step** -- one row-to-row jump accounts for at least `_MIN_STEP_SHARE` of that
  spread. A composited edge is abrupt; a sunset gradient spreads the same total
  change over every row and fails this.

Measured on the fixtures in `tests/test_wave8.py` (spread/median, step share):
sky over grass 0.09 / 0.75 and sky over city 0.13 / 0.92 -- both rejected on
spread; a bright score bug 1.11 / 1.00, a flat dark lower-third 1.02 / 0.93 and a
band-filling overlay 1.07 / 0.82 -- all caught. A strong in-band gradient clears
spread and is rejected on step.

**#721: the step is necessary, not sufficient.** A horizon at 65-90% of frame
height is also a full-width luminance step, and passes both gates. The
discriminator is temporal: a composited overlay is pixel-identical between two
frames a second apart; footage is not. For each of `_COLUMNS` columns, the share of
static pixels (|luma diff| <= `_STATIC_PX`) in the bottom band is compared with
the same column in the frame above it. An overlay column is static where the
footage above it moves.

Measured on five real Pexels clips (`assets/cache`, frames at 0s and 1s), max
column excess: flat sky pasted over everything above 65/70/80/90% of height reads
-0.64 .. +0.05; overlays composited identically onto both frames that also clear
the spatial gates read +0.36 .. +0.77. Raw clips alone reach +0.57 (a strip of
still ground), which is why the temporal check *confirms* the spatial one and never
replaces it. One clip is locked-off (0.96 of the frame above the band static), so it
reads `no_motion`.

Known gap, deliberately on the safe side: an overlay under a perfectly still sky
reads as no excess (the column above is static too), so its captions stay at the
bottom. Deliberately no face detection: a face is not an overlay.
"""

from __future__ import annotations

from typing import Any

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
# 0.13/0.12/0.13, so x3 costs nothing there.
_WINDOW_BANDS = 3

# #721 temporal confirmation.
_SECOND_FRAME_S = 1.0
# A pixel whose luma moved by no more than this is static. h264 wobble on a
# composited graphic stays well under it.
_STATIC_PX = 8.0
_COLUMNS = 8
# Band column static share minus the same column above. Horizons measured <= +0.05.
# #727: 0.25 missed 4 real NBA 2K score bars at 0.19-0.22; on 30 labelled bars, 50
# stock clips and 12 hybrids, 0.18 finds 26/30 (was 22) and adds no new TOP.
_MIN_STATIC_EXCESS = 0.18
# Above this share of static pixels over the band there is no motion to compare.
_MAX_ABOVE_STATIC = 0.85

# #726: measure the frame the render shows. The render is 1080x1920 (9:16); measuring
# at half that is plenty for per-row means and keeps the pixel loops cheap.
_RENDER_ASPECT = 9 / 16
_MEASURE_MAX_H = 960


def _luma(pixel) -> float:
    r, g, b = pixel[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


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
            total += _luma(rgb.getpixel((x, y)))
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


def _spatial(rgb) -> tuple[str, tuple[float, float] | None]:
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


def render_crop(image):
    """#726: the part of a frame the render actually shows, at measuring size.

    `video/render_video.py` cover-scales every background to 1080x1920 and centre-crops
    (`force_original_aspect_ratio=increase,crop`), so a 16:9 clip keeps only its middle
    ~32% of width. Measuring the uncropped source let an overlay in the discarded
    margins move captions for something no viewer sees. Both frames of a pair go
    through this, so spatial and temporal readings see identical pixels.
    """
    rgb = image.convert("RGB")
    width, height = rgb.size
    if width <= 0 or height <= 0:
        return rgb
    aspect = width / height
    if abs(aspect - _RENDER_ASPECT) > 0.01:
        if aspect > _RENDER_ASPECT:
            new_w = max(1, round(height * _RENDER_ASPECT))
            left = (width - new_w) // 2
            rgb = rgb.crop((left, 0, left + new_w, height))
        else:
            new_h = max(1, round(width / _RENDER_ASPECT))
            top = (height - new_h) // 2
            rgb = rgb.crop((0, top, width, top + new_h))
    if rgb.size[1] > _MEASURE_MAX_H:
        scale = _MEASURE_MAX_H / rgb.size[1]
        rgb = rgb.resize((max(1, round(rgb.size[0] * scale)), _MEASURE_MAX_H))
    return rgb


def _frame_at(path: str, seconds: float):
    try:
        from core.hud_detect import _load_frame_at
    except Exception as exc:
        logger.debug("caption-place imports skipped: %s", exc)
        return None
    image = _load_frame_at(path, seconds)
    return render_crop(image) if image is not None else None


def band_reading(path: str | None) -> tuple[str, tuple[float, float] | None]:
    """(state, metrics) for the spatial gate. State is 'ok', 'no_frame' or 'no_contrast'.

    The three are different answers and were worth separating: a path that yields
    no frame is a usage error, while a band that is flat or pure black is a
    *measured* result whose operational meaning is "captions stay at the bottom".
    """
    if not path:
        return "no_frame", None
    rgb = _frame_at(path, 0.0)
    if rgb is None:
        return "no_frame", None
    return _spatial(rgb)


def band_overlay_metrics(path: str | None) -> tuple[float, float] | None:
    """(spread/median, step share) for the bottom band, or None when unmeasurable."""
    return band_reading(path)[1]


def _passes_step(metrics: tuple[float, float] | None) -> bool:
    if metrics is None:
        return False
    spread_ratio, step_share = metrics
    return spread_ratio >= _MIN_SPREAD and step_share >= _MIN_STEP_SHARE


def _static_share(a, b, y0: int, y1: int, x0: int, x1: int) -> float:
    step_x = max(1, a.size[0] // 64)
    step_y = max(1, (y1 - y0) // 32 or 1)
    total = static = 0
    for y in range(y0, y1, step_y):
        for x in range(x0, x1, step_x):
            total += 1
            if abs(_luma(a.getpixel((x, y))) - _luma(b.getpixel((x, y)))) <= _STATIC_PX:
                static += 1
    return static / total if total else 0.0


def temporal_reading(frame_a, frame_b) -> tuple[float, float] | None:
    """(static share of the frame above the band, max column static excess).

    None when the two frames cannot be compared.
    """
    if frame_a is None or frame_b is None:
        return None
    a = frame_a.convert("RGB")
    b = frame_b.convert("RGB")
    if a.size != b.size:
        return None
    width, height = a.size
    if width < _COLUMNS or height < 16:
        return None
    band_top = height - max(8, height // 8)
    above = _static_share(a, b, 0, band_top, 0, width)
    excess = -1.0
    for col in range(_COLUMNS):
        x0 = col * width // _COLUMNS
        x1 = (col + 1) * width // _COLUMNS
        in_band = _static_share(a, b, band_top, height, x0, x1)
        over_it = _static_share(a, b, 0, band_top, x0, x1)
        excess = max(excess, in_band - over_it)
    return above, excess


def motion_reading(frame_a, frame_b) -> tuple[str, float | None]:
    """('ok', excess) when the footage moves; ('no_motion', ...) when it cannot say."""
    reading = temporal_reading(frame_a, frame_b)
    if reading is None:
        return "no_motion", None
    above, excess = reading
    if above > _MAX_ABOVE_STATIC:
        return "no_motion", excess
    return "ok", excess


def frames_show_static_overlay(frame_a, frame_b) -> bool:
    state, excess = motion_reading(frame_a, frame_b)
    return state == "ok" and excess is not None and excess >= _MIN_STATIC_EXCESS


def overlay_reading(path: str | None, *, always_motion: bool = False) -> dict[str, Any]:
    """Everything the decision used, so `ops caption-anchor` prints the same numbers.

    The second frame is only decoded when the spatial gate passes, unless
    `always_motion` asks for it anyway.
    """
    out: dict[str, Any] = {
        "spatial": "no_frame",
        "metrics": None,
        # The #717 gate alone: necessary, not sufficient (#721).
        "step": False,
        "motion": "no_motion",
        "excess": None,
        "overlay": False,
    }
    if not path:
        return out
    first = _frame_at(path, 0.0)
    if first is None:
        return out
    out["spatial"], out["metrics"] = _spatial(first)
    step = out["spatial"] == "ok" and _passes_step(out["metrics"])
    out["step"] = step
    if not (step or always_motion):
        return out
    second = _frame_at(path, _SECOND_FRAME_S)
    out["motion"], out["excess"] = motion_reading(first, second)
    out["overlay"] = step and frames_show_static_overlay(first, second)
    return out


def bottom_band_overlay(path: str | None) -> bool:
    """True when the bottom caption band carries a composited overlay: a spatial
    step (#717) that stays still while the footage around it moves (#721).

    Independent of the flag so it can be measured directly; `choose_caption_anchor`
    is what respects `CAPTION_AUTO_PLACE`.
    """
    return bool(overlay_reading(path)["overlay"])


def choose_caption_anchor(path: str | None) -> str:
    """'top' when the default bottom caption band is occupied, else 'bottom'."""
    if not path:
        return "bottom"
    from core.providers import flag_enabled

    if not flag_enabled("CAPTION_AUTO_PLACE", default=False):
        return "bottom"
    try:
        return "top" if bottom_band_overlay(path) else "bottom"
    except Exception as exc:
        logger.debug("caption placement skipped: %s", exc)
        return "bottom"
