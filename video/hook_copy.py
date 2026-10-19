"""Wave 113 (#1417, #1419): the TikTok and Instagram copy starts at the first word.

Buffer measured TikTok's viewers watching 1.24-1.68 s on average, and every TapIn video opens on a
2.15 s channel intro - they left before the hook. The copy sent through Buffer is cut at the run's
own intro; YouTube keeps its intro test (#988, INTRO_TEST).

week_compile cut the channel's 2.15 s from every Short, so a Short rendered without the intro lost
its hook. Both read `hook_offset`, which knows what each run actually opened on.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from typing import Any

from core.logging import get_logger

logger = get_logger("video.hook_copy")

_TIMEOUT = 600


def run_opening(run: Any) -> dict[str, Any]:
    """The run's opening record - {"intro": bool, "intro_seconds": s} - kept in its quality by
    the render (#988, `channel_intro.opening_record`); {} when there is none."""
    try:
        quality = json.loads(getattr(run, "quality_json", "") or "{}")
    except (TypeError, ValueError):
        return {}
    opening = quality.get("opening") if isinstance(quality, dict) else None
    return opening if isinstance(opening, dict) else {}


def hook_offset(
    opening: dict[str, Any] | None, channel_id: str | None, *, default: float | None = None
) -> float:
    """Seconds before the first word: the run's recorded intro (`run_opening`), 0 when it had
    none, and the channel's offset (or `default`) only for a run from before the intro was
    recorded - they all had one."""
    feats = opening or {}
    if "intro" in feats:
        if not feats.get("intro"):
            return 0.0
        try:
            seconds = float(feats.get("intro_seconds") or 0.0)
        except (TypeError, ValueError):
            seconds = 0.0
        if seconds > 0:
            return round(seconds, 2)
    if default is not None:
        return float(default)
    from video.intro_offset import intro_offset_seconds

    return intro_offset_seconds(channel_id)


def hook_copy_path(src: str) -> str:
    stem, ext = os.path.splitext(src)
    return f"{stem}.hook{ext or '.mp4'}"


def hook_copy_argv(src: str, dst: str, *, offset: float) -> list[str]:
    """Re-encoded from `offset` (a stream copy would start on the keyframe before it)."""
    return [
        "ffmpeg", "-nostdin", "-y", "-ss", f"{offset:.2f}", "-i", src,
        "-map", "0:v", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst,
    ]  # fmt: skip


def ensure_hook_copy(
    src: str,
    opening: dict[str, Any] | None,
    channel_id: str | None,
    *,
    run: Callable[..., Any] = subprocess.run,
) -> str:
    """The file to send: `src` when there is no intro to cut, else `<stem>.hook.mp4`, made once.
    Fail-open: any failure sends `src`, as before."""
    offset = hook_offset(opening, channel_id)
    if offset <= 0 or not src or not os.path.isfile(src):
        return src
    dst = hook_copy_path(src)
    try:
        if os.path.isfile(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
            return dst
        done = run(hook_copy_argv(src, dst, offset=offset), capture_output=True,
                   stdin=subprocess.DEVNULL, timeout=_TIMEOUT, check=False)  # fmt: skip
        if getattr(done, "returncode", 1) == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 0:
            return dst
        logger.warning(
            "hook copy of %s not made (ffmpeg exit %s)", src, getattr(done, "returncode", "?")
        )
    except Exception as exc:
        logger.warning("hook copy of %s not made: %s", src, exc)
    return src
