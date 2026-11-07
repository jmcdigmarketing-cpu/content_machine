"""#1629 (B02.8, wave 156): a game's stills are its footage when no gameplay of it is owned.

Live 11-06: `Marvel's Spider-Man 2` held three of the operator's screenshots and no video, so the
library never counted it - a Spider-Man 2 story would cut a mix of other games (runs 175 and 224
cut that mix under a Final Fantasy and a Mass Effect story). Each still becomes one slow-zoom
vertical clip beside it, `<stem>.still.mp4`, made once in overnight's library step
(`clip_ingest.measure_library`); the folder then reads as that game's footage and its clips are
measured like any other. A still clip never reads as a menu by its low motion
(`clip_tags.is_ui_clip`). `STILL_CLIPS=false` turns it off (the suite does).
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from core.logging import get_logger

logger = get_logger("assets.stills")

STILL_SECONDS = 4.0
STILL_SUFFIX = ".still.mp4"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
_SIZE = "1080x1920"


def enabled() -> bool:
    return os.getenv("STILL_CLIPS", "true").strip().lower() not in ("0", "false", "no", "off")


def is_still_clip(path: str) -> bool:
    return str(path or "").lower().endswith(STILL_SUFFIX)


def still_argv(image: str, dst: str, *, seconds: float = STILL_SECONDS) -> list[str]:
    """One still as a vertical clip: cover-cropped to 9:16, then a slow centred zoom to 1.1x."""
    frames = max(1, int(round(seconds * 30)))
    graph = (
        "scale=1188:2112:force_original_aspect_ratio=increase,crop=1188:2112,"
        f"zoompan=z='min(1+{0.1 / frames:.5f}*on,1.1)':x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':d=1:s={_SIZE}:fps=30,format=yuv420p"
    )
    length = f"{seconds:g}"
    return [
        "ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30",
        "-t", length, "-i", image, "-vf", graph, "-t", length, "-an", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "20", "-movflags", "+faststart", dst,
    ]  # fmt: skip


def still_clip_path(image: str) -> str:
    return os.path.splitext(image)[0] + STILL_SUFFIX


def make_still_clips(library_root: str, *, run: Any = None) -> list[str]:
    """Make the missing still clip of each image under `library_root`; the paths made. A failed
    still is skipped (and tried again next night). Never raises."""
    made: list[str] = []
    runner = run or subprocess.run
    try:
        walked = list(os.walk(library_root)) if os.path.isdir(library_root) else []
    except OSError as exc:
        logger.debug("stills not read under %s: %s", library_root, exc)
        return made
    for folder, _dirs, files in walked:
        for name in sorted(files):
            if not name.lower().endswith(IMAGE_EXTS):
                continue
            image = os.path.join(folder, name)
            dst = still_clip_path(image)
            if os.path.isfile(dst):
                continue
            try:
                done = runner(still_argv(image, dst), capture_output=True, timeout=180,
                              stdin=subprocess.DEVNULL, check=False)  # fmt: skip
            except Exception as exc:
                logger.warning("still clip not made for %s: %s", image, exc)
                continue
            if getattr(done, "returncode", 1) == 0 and os.path.isfile(dst):
                made.append(dst)
            else:
                logger.warning("still clip not made for %s (ffmpeg exit %s)", image,
                               getattr(done, "returncode", "?"))  # fmt: skip
    return made
