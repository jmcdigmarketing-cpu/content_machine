"""Shared H.264 encode argv: NVENC when probed, else libx264.

Encode is candidate 38. `ffmpeg_has_nvenc()` is capability-only; this module is
the one that actually switches `-c:v`. `NVENC=off` keeps the historical
libx264 block byte-identical. A failed NVENC encode retries once with libx264
(same fail-open as a music-bed miss falling back to VO-only).
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from typing import Any

from core.logging import get_logger

logger = get_logger("video.encoder")

_OFF = frozenset({"0", "off", "false", "no"})
_NVENC_FOLLOW_FLAGS = frozenset({"-preset", "-cq", "-crf", "-rc", "-b:v", "-gpu", "-tune"})


def nvenc_wanted() -> bool:
    raw = (os.getenv("NVENC") or "").strip().lower()
    if raw in _OFF:
        return False
    from core.cuda_probe import ffmpeg_has_nvenc

    return bool(ffmpeg_has_nvenc())


def video_encoder_args(*, preset: str = "fast", crf: str | int = "23") -> list[str]:
    crf_s = str(crf)
    if nvenc_wanted():
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", crf_s]
    return ["-c:v", "libx264", "-preset", preset, "-crf", crf_s]


def fallback_libx264_cmd(
    cmd: list[str], *, preset: str = "fast", crf: str | int = "23"
) -> list[str]:
    """Replace an h264_nvenc encoder block with the CPU libx264 block."""
    out = list(cmd)
    if "h264_nvenc" not in out:
        return out
    i = out.index("h264_nvenc")
    start = i - 1 if i and out[i - 1] == "-c:v" else i
    k = i + 1
    while k + 1 < len(out) and out[k] in _NVENC_FOLLOW_FLAGS:
        k += 2
    out[start:k] = ["-c:v", "libx264", "-preset", preset, "-crf", str(crf)]
    return out


# Candidate 309 persists the argv that SUCCEEDED, never a reconstructed one. When
# NVENC fails and libx264 retries, the process that comes back is the retry's --
# stamp the argv that actually ran on it so the booth cannot show (and the
# operator cannot copy) the h264_nvenc command that failed.
_EXECUTED_ATTR = "_content_os_executed_cmd"


def mark_executed(process: Any, cmd: list[str]) -> Any:
    try:
        setattr(process, _EXECUTED_ATTR, list(cmd))
    except Exception as exc:  # frozen/slotted return types stay usable
        logger.debug("executed-argv stamp skipped: %s", exc)
    return process


def executed_cmd(process: Any, cmd: list[str]) -> list[str]:
    """The argv that actually ran -- the libx264 retry when NVENC fell back."""
    stamped = getattr(process, _EXECUTED_ATTR, None)
    return list(stamped) if stamped else list(cmd)


def _default_runner(cmd: list[str]) -> Any:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_ffmpeg_with_nvenc_fallback(
    cmd: list[str],
    *,
    runner: Callable[[list[str]], Any] | None = None,
    preset: str = "fast",
    crf: str | int = "23",
) -> Any:
    """Run `cmd`; if it used NVENC and failed, retry once with libx264."""
    run = runner or _default_runner
    process = run(cmd)
    if getattr(process, "returncode", 1) == 0:
        return mark_executed(process, cmd)
    if "h264_nvenc" not in cmd:
        return mark_executed(process, cmd)
    fallback = fallback_libx264_cmd(cmd, preset=preset, crf=crf)
    logger.warning("NVENC encode failed — retrying libx264")
    return mark_executed(run(fallback), fallback)
