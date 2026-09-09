"""#415: 2s synthetic encode through the production ffmpeg command."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from core.logging import get_logger

logger = get_logger("video.render_smoke")


def require_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    if os.getenv("CI", "").strip().lower() in ("1", "true", "yes"):
        raise RuntimeError("ffmpeg is required in CI for the render smoke (#415)")
    raise RuntimeError("ffmpeg is not on PATH")


def smoke_render_synthetic(dest_dir: str) -> Path:
    """Encode a 2s lavfi clip with the production subtitle filtergraph."""
    ffmpeg = require_ffmpeg()
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    video = dest / "src.mp4"
    audio = dest / "vo.mp3"
    subs = dest / "captions.ass"
    out = dest / "smoke.mp4"

    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x568:r=30:d=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            str(audio),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    from video.caption_timing import build_ass_karaoke

    subs.write_text(
        build_ass_karaoke([{"word": "Hi", "start": 0.0, "end": 0.4}], max_words=2),
        encoding="utf-8",
    )
    from video.render_video import build_render_ffmpeg_command

    cmd = build_render_ffmpeg_command(
        background_path=str(video),
        mp3_path=str(audio),
        output_path=str(out),
        subtitle_path=str(subs),
        duration=2.0,
        render_preset="draft",
    )
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    return out
