"""#683: detect a HUD overlay from a still or first video frame."""

from __future__ import annotations

from pathlib import Path

from core.logging import get_logger

logger = get_logger("core.hud_detect")

_VIDEO = {".mp4", ".mov", ".mkv", ".webm"}

# Process-local memo. An overnight batch renders many drafts in one interpreter and
# assign_owned_clips re-probes the same legacy clips for each of them; the answer
# only changes when the file does, so key on (path, mtime, size).
_PROBED: dict[tuple[str, float, int], bool] = {}


def _probe_key(path: str) -> tuple[str, float, int] | None:
    try:
        stat = Path(path).stat()
    except OSError:
        return None
    return (str(Path(path).resolve()), stat.st_mtime, stat.st_size)


def detect_hud(path: str) -> bool:
    """True when the top band is much more colourful than the rest of the frame."""
    key = _probe_key(path)
    if key is not None and key in _PROBED:
        return _PROBED[key]
    verdict = _detect_hud_uncached(path)
    if key is not None:
        _PROBED[key] = verdict
    return verdict


def _detect_hud_uncached(path: str) -> bool:
    image = _load_frame(path)
    if image is None:
        return False
    rgb = image.convert("RGB")
    width, height = rgb.size
    if width < 8 or height < 8:
        return False
    band = max(2, height // 8)
    top_colors = _unique_chroma(rgb, 0, band)
    body_colors = _unique_chroma(rgb, band, height)
    return top_colors >= 12 and top_colors > body_colors * 2


def _load_frame(path: str):
    from PIL import Image

    target = Path(path)
    if not target.is_file():
        return None
    if target.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        return Image.open(target)
    if target.suffix.lower() not in _VIDEO:
        return None
    import shutil
    import subprocess
    import tempfile

    # assign_owned_clips calls this from the render path, once per clip whose index
    # entry predates #683. Every mkdtemp that is not removed is one leaked directory
    # per clip per render — so the frame is copied into memory and the directory goes.
    work = tempfile.mkdtemp(prefix="hud-probe-")
    try:
        dest = Path(work) / "frame.png"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(target),
                "-vframes",
                "1",
                str(dest),
            ],
            capture_output=True,
            check=False,
            timeout=8,
        )
        if dest.is_file():
            with Image.open(dest) as frame:
                return frame.copy()
    except Exception as exc:
        logger.debug("hud frame grab skipped: %s", exc)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return None


def _unique_chroma(image, y0: int, y1: int) -> int:
    seen: set[tuple[int, int, int]] = set()
    width, _height = image.size
    step = max(1, width // 32)
    for y in range(y0, y1, max(1, (y1 - y0) // 8 or 1)):
        for x in range(0, width, step):
            r, g, b = image.getpixel((x, y))[:3]
            if max(r, g, b) - min(r, g, b) < 18:
                continue
            seen.add((r // 16, g // 16, b // 16))
    return len(seen)
