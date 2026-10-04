"""A plain branded background for a topic no footage matches (#955).

When no owned folder is the topic's game or sport and no stock clip came back, the render
failed outright ("No background video found"), and before #955 it never got that far: the
footage chooser took a random game folder. It now draws the channel's end-card colour at
1080x1920 for the voice's length. The render's own look (grade, grain, vignette) and the
captions go on top, so the video still reads as the channel's - never as another game.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from typing import Any

from assets.types import AssetResult
from core.logging import get_logger

logger = get_logger("assets.plain_background")

TARGET_W = 1080
TARGET_H = 1920
_DEFAULT_COLOUR = "#111318"
_HEX = frozenset("0123456789abcdefABCDEF")


def _colour(channel_id: str | None) -> str:
    """The channel's end-card background colour (config/design_tokens.json)."""
    try:
        from core.design_tokens import channel_tokens

        value = str(channel_tokens(channel_id or "default").get("end_card_bg") or "")
    except Exception as exc:
        logger.debug("plain background colour skipped: %s", exc)
        value = ""
    if len(value) == 7 and value.startswith("#") and set(value[1:]) <= _HEX:
        return value
    return _DEFAULT_COLOUR


def _out_dir() -> str:
    """Beside fast cut's composed backgrounds, so the same pruning clears it (#797)."""
    from config.paths import DATA_DIR, ensure_data_dir

    ensure_data_dir()
    path = os.path.join(DATA_DIR, "tmp", "hybrid_backgrounds")
    os.makedirs(path, exist_ok=True)
    return path


def build_plain_command(colour: str, duration: float, output: str) -> list[str]:
    from video.encoder import video_encoder_args

    return [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c={colour}:s={TARGET_W}x{TARGET_H}:r=30:d={duration:.3f}",
        *video_encoder_args(),
        "-pix_fmt",
        "yuv420p",
        "-an",
        output,
    ]


def plain_background(
    channel_id: str | None,
    duration: float | None,
    *,
    runner: Callable[[list[str]], Any] | None = None,
) -> AssetResult | None:
    """Draw the plain background; None when FFmpeg fails (the caller then raises)."""
    seconds = float(duration) if duration and duration > 0 else 60.0
    output = os.path.join(_out_dir(), f"plain_{uuid.uuid4().hex[:12]}.mp4")
    cmd = build_plain_command(_colour(channel_id), max(seconds, 1.0), output)
    try:
        from video.encoder import run_ffmpeg_with_nvenc_fallback

        process = run_ffmpeg_with_nvenc_fallback(cmd, runner=runner)
    except Exception as exc:
        logger.warning("plain background failed: %s", exc)
        return None
    if getattr(process, "returncode", 1) != 0 or not os.path.isfile(output):
        tail = str(getattr(process, "stderr", "") or "")[-300:]
        logger.warning("plain background failed: %s", tail)
        return None
    return AssetResult(
        path=output,
        provider="plain",
        source_id="footage:plain:",
        query="",
        attribution="Plain background (no footage matches the topic)",
    )
