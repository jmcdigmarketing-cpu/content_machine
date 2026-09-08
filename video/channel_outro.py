"""Generate and append a per-channel publish end card with FFmpeg."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from config.channels import get_channel_profile
from core.logging import get_logger
from video.encoder import (
    executed_cmd,
    run_ffmpeg_with_nvenc_fallback,
    video_encoder_args,
)

logger = get_logger("video.channel_outro")

TARGET_W = 1080
TARGET_H = 1920
# YouTube Shorts chrome: top ~12%, captions + subscribe sit in the bottom 20%.
_SAFE_TOP = 0.12
_SAFE_BOTTOM = 0.20


def _hex(value: Any, default: str) -> str:
    text = str(value or default).strip()
    if (
        len(text) == 7
        and text.startswith("#")
        and all(ch in "0123456789abcdefABCDEF" for ch in text[1:])
    ):
        return text
    return default


def resolve_end_card(channel_id: str | None = None) -> dict[str, Any] | None:
    """Return a bounded valid card, or None while making malformed config visible."""
    raw = dict(get_channel_profile(channel_id).end_card or {})
    if not raw or not bool(raw.get("enabled", False)):
        return None
    try:
        duration = float(raw.get("duration", 0))
    except (TypeError, ValueError):
        logger.warning("End card skipped: duration is not numeric for channel=%s", channel_id)
        return None
    text = str(raw.get("text") or "").strip()
    if not text or not (0.5 <= duration <= 10.0):
        logger.warning("End card skipped: invalid text/duration for channel=%s", channel_id)
        return None
    return {
        "enabled": True,
        "duration": duration,
        "text": text[:100],
        "bg": _hex(raw.get("bg"), "#000000"),
        "fg": _hex(raw.get("fg"), "#FFFFFF"),
    }


def end_card_text_y(text_h: int) -> int:
    """Vertical origin for end-card copy: inside the band captions do not occupy."""
    top = int(TARGET_H * _SAFE_TOP)
    bottom = int(TARGET_H * (1.0 - _SAFE_BOTTOM))
    height = max(1, int(text_h))
    y = top + max(0, (bottom - top - height) // 2)
    return max(top, min(y, bottom - height))


def _drawtext_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'").replace("%", r"\%")


def _font_file() -> str | None:
    candidates = [
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arialbd.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    return next((path for path in candidates if os.path.isfile(path)), None)


def build_outro_concat_command(
    *, body_path: str, output_path: str, card: dict[str, Any]
) -> list[str]:
    duration = float(card["duration"])
    text = _drawtext_escape(str(card["text"]))
    bg = str(card["bg"]).replace("#", "0x")
    fg = str(card["fg"]).replace("#", "0x")
    font_path = _font_file()
    font_opt = ""
    if font_path:
        escaped_font = font_path.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        font_opt = f"fontfile='{escaped_font}':"
    scale = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},setsar=1,fps=30"
    )
    graph = (
        f"[0:v]{scale},setpts=PTS-STARTPTS[v0];"
        f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo[a0];"
        f"[1:v]drawtext={font_opt}text='{text}':fontcolor={fg}:fontsize=64:"
        "x=(w-text_w)/2:"
        f"y=h*{_SAFE_TOP:.2f}+(h*{1.0 - _SAFE_TOP - _SAFE_BOTTOM:.2f}-text_h)/2,"
        f"setpts=PTS-STARTPTS[v1];"
        f"[2:a]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]"
    )
    return [
        "ffmpeg",
        "-y",
        "-i",
        body_path,
        "-f",
        "lavfi",
        "-i",
        f"color=c={bg}:s={TARGET_W}x{TARGET_H}:r=30:d={duration:.3f}",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=48000:cl=stereo",
        "-filter_complex",
        graph,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        *video_encoder_args(),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        output_path,
    ]


def append_channel_outro(
    body_path: str,
    *,
    channel_id: str | None = None,
    output_path: str | None = None,
    command_callback: Callable[[str, list[str]], None] | None = None,
) -> str:
    """Append the generated card, restoring an in-place body on every failure path."""
    card = resolve_end_card(channel_id)
    if not card:
        return body_path
    body_path = os.path.abspath(body_path)
    if not os.path.isfile(body_path):
        raise FileNotFoundError(body_path)
    final_path = os.path.abspath(output_path or body_path)
    work_body = body_path
    temp_body = ""
    if final_path == body_path:
        temp_body = body_path + ".body.outro.tmp.mp4"
        work_body = temp_body
        from core.file_lock import retry_locked

        retry_locked(lambda: os.replace(body_path, temp_body))

    cmd = build_outro_concat_command(body_path=work_body, output_path=final_path, card=card)
    if command_callback is not None:
        try:
            command_callback("outro_attempt", list(cmd))
        except Exception as exc:
            logger.debug("outro attempt capture skipped: %s", exc)

    concat_ok = False
    try:
        process = run_ffmpeg_with_nvenc_fallback(cmd)
        if process.returncode != 0:
            raise RuntimeError(f"End-card concat failed: {(process.stderr or '')[-800:]}")
        if not os.path.isfile(final_path) or os.path.getsize(final_path) == 0:
            raise RuntimeError(f"End-card concat wrote no usable file: {final_path}")
        concat_ok = True
        if command_callback is not None:
            try:
                command_callback("outro_success", executed_cmd(process, cmd))
            except Exception as exc:
                logger.debug("outro success capture skipped: %s", exc)
    finally:
        if not concat_ok and temp_body and os.path.isfile(temp_body):
            os.replace(temp_body, body_path)

    if temp_body and os.path.isfile(temp_body):
        try:
            os.remove(temp_body)
        except OSError as exc:
            logger.warning("Could not remove outro temp body %s: %s", temp_body, exc)
    return final_path
