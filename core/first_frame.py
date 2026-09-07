"""#513. Reject a black or frozen first frame before YouTube auto-thumbs it.

Advisory: fail-visible, never a silent skip of a real upload. Sample the
finished file after any intro sting so the sting itself is not the 'video'.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from core.logging import get_logger

logger = get_logger("core.first_frame")

BLACK_LUMA = 8.0
FROZEN_MEAN_DIFF = 1.5


@dataclass(frozen=True)
class FirstFrameCheck:
    black: bool
    frozen: bool
    mean_luma: float
    detail: str
    path: str = ""


def inspect_frame(path: str | Path) -> FirstFrameCheck:
    """Pillow check on a still. Used by tests and by inspect_video after a grab."""
    source = str(path)
    with Image.open(source) as image:
        gray = image.convert("L")
        mean = float(ImageStat.Stat(gray).mean[0])
    black = mean < BLACK_LUMA
    detail = "first frame is black" if black else "first frame has visible content"
    return FirstFrameCheck(
        black=black,
        frozen=False,
        mean_luma=round(mean, 2),
        detail=detail,
        path=source,
    )


def inspect_frames(first: str | Path, second: str | Path) -> FirstFrameCheck:
    """Two stills: black on the first, frozen if they are nearly identical."""
    a = inspect_frame(first)
    with Image.open(first) as im_a, Image.open(second) as im_b:
        gray_a = im_a.convert("L")
        gray_b = im_b.convert("L").resize(gray_a.size)
        diff = ImageChops.difference(gray_a, gray_b)
        mean_diff = float(ImageStat.Stat(diff).mean[0])
    frozen = mean_diff < FROZEN_MEAN_DIFF
    if a.black:
        detail = "first frame is black"
    elif frozen:
        detail = "first frames are frozen (identical)"
    else:
        detail = "first frame has visible content"
    return FirstFrameCheck(
        black=a.black,
        frozen=frozen,
        mean_luma=a.mean_luma,
        detail=detail,
        path=str(first),
    )


def render_check(check: FirstFrameCheck) -> str:
    if check.black:
        status = "BLACK"
    elif check.frozen:
        status = "FROZEN"
    else:
        status = "OK"
    return (
        f"First frame ADVISORY: {status} - {check.detail} "
        f"(luma {check.mean_luma:.1f}; not a publish block)"
    )


def inspect_video(path: str | Path, *, intro_offset: float = 0.0) -> FirstFrameCheck | None:
    """Grab two frames from the finished mp4 using output-seek. Fail-open."""
    source = str(path)
    if not os.path.isfile(source):
        return None
    try:
        from scripts.probe_sync import grab_frame
    except Exception as exc:
        logger.debug("grab_frame import skipped: %s", exc)
        return None
    at = max(0.0, float(intro_offset))
    with tempfile.TemporaryDirectory() as tmp:
        a = os.path.join(tmp, "a.png")
        b = os.path.join(tmp, "b.png")
        if not grab_frame(source, at, a):
            logger.warning("first-frame grab failed for %s", source)
            return None
        if not grab_frame(source, at + 0.35, b) or not os.path.isfile(b):
            return inspect_frame(a)
        return inspect_frames(a, b)
