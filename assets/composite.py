"""
Compose hybrid backgrounds: local gameplay footage + stock B-roll in one vertical clip.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from typing import List, Optional

from assets.types import AssetResult
from config.paths import DATA_DIR, ensure_data_dir
from core.logging import get_logger

logger = get_logger("assets.composite")

TARGET_W = 1080
TARGET_H = 1920


def build_hybrid_concat_command(
    *,
    local_path: str,
    stock_path: str,
    output_path: str,
    duration: float,
    local_ratio: float = 0.45,
) -> List[str]:
    """FFmpeg: loop both inputs, scale/crop, concat local segment then stock (no audio)."""
    ratio = max(0.15, min(local_ratio, 0.85))
    local_dur = duration * ratio
    stock_dur = max(0.1, duration - local_dur)

    # Normalize fps + yuv420p before concat (avoids libx264 "external library" errors
    # when mixing HEVC/MOV local clips with stock MP4 on Windows).
    filter_complex = (
        f"[0:v]fps=30,scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},format=yuv420p,trim=duration={local_dur:.3f},"
        f"setpts=PTS-STARTPTS[v0];"
        f"[1:v]fps=30,scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},format=yuv420p,trim=duration={stock_dur:.3f},"
        f"setpts=PTS-STARTPTS[v1];"
        f"[v0][v1]concat=n=2:v=1:a=0,format=yuv420p[vout]"
    )

    return [
        "ffmpeg",
        "-y",
        "-hwaccel",
        "none",
        "-stream_loop",
        "-1",
        "-i",
        local_path,
        "-hwaccel",
        "none",
        "-stream_loop",
        "-1",
        "-i",
        stock_path,
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-t",
        f"{duration:.3f}",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-an",
        output_path,
    ]


def _temp_output_path() -> str:
    ensure_data_dir()
    tmp_dir = os.path.join(DATA_DIR, "tmp", "hybrid_backgrounds")
    os.makedirs(tmp_dir, exist_ok=True)
    return os.path.join(tmp_dir, f"hybrid_{uuid.uuid4().hex[:12]}.mp4")


def compose_hybrid_background(
    local: AssetResult,
    stock: AssetResult,
    duration: float,
    *,
    local_ratio: float = 0.45,
) -> AssetResult:
    """Merge local gameplay + stock into one background file for render_vertical_video."""
    output_path = _temp_output_path()
    cmd = build_hybrid_concat_command(
        local_path=os.path.abspath(local.path),
        stock_path=os.path.abspath(stock.path),
        output_path=output_path,
        duration=duration,
        local_ratio=local_ratio,
    )

    logger.info(
        "Composing hybrid background (local %.0f%% / stock %.0f%%)",
        local_ratio * 100,
        (1 - local_ratio) * 100,
    )
    process = subprocess.run(cmd, capture_output=True, text=True)
    if process.returncode != 0:
        if os.path.isfile(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        raise RuntimeError(
            f"Hybrid background compose failed: {(process.stderr or '')[-800:]}"
        )

    attribution = stock.attribution
    if local.provider == "local" and stock.attribution:
        attribution = f"Gameplay (local) + {stock.attribution}"

    return AssetResult(
        path=output_path,
        provider="hybrid",
        query=local.query or stock.query,
        attribution=attribution,
    )


def try_compose_hybrid(
    local: Optional[AssetResult],
    stock: Optional[AssetResult],
    duration: float,
    *,
    local_ratio: float,
) -> Optional[AssetResult]:
    if not (local and stock):
        return None
    try:
        return compose_hybrid_background(
            local, stock, duration, local_ratio=local_ratio
        )
    except RuntimeError as exc:
        logger.warning(
            "Hybrid background compose failed; will use stock or local only: %s",
            exc,
        )
        return None
