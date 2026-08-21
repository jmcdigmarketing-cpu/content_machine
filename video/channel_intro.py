"""
Prepend a channel intro clip to rendered vertical videos (FFmpeg).

Intro path resolution (first match):
  1. ChannelProfile.intro_video_file (relative to repo root)
  2. CHANNEL_INTRO_PATH env
  3. video/intro/channel_intro.mp4
"""

from __future__ import annotations

import os
import subprocess

from config.channels import get_channel_profile, resolve_channel_id
from config.paths import ROOT_DIR
from core.logging import get_logger

logger = get_logger("video.channel_intro")

TARGET_W = 1080
TARGET_H = 1920

DEFAULT_INTRO_REL = os.path.join("video", "intro", "channel_intro.mp4")


def _intro_enabled() -> bool:
    return os.getenv("CHANNEL_INTRO_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def _abs_from_root(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(ROOT_DIR, path)


def resolve_intro_path(channel_id: str | None = None) -> str | None:
    """Return absolute path to intro MP4 if configured and file exists."""
    if not _intro_enabled():
        return None

    channel_id = resolve_channel_id(channel_id)
    profile = get_channel_profile(channel_id)
    candidates: list[str] = []

    if profile.intro_video_file:
        candidates.append(_abs_from_root(profile.intro_video_file))

    env_path = os.getenv("CHANNEL_INTRO_PATH", "").strip()
    if env_path:
        candidates.append(_abs_from_root(env_path))

    candidates.append(_abs_from_root(DEFAULT_INTRO_REL))

    for path in candidates:
        if path and os.path.isfile(path):
            return os.path.abspath(path)

    logger.debug("No channel intro file found for channel=%s", channel_id)
    return None


def _probe_duration(path: str) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (ValueError, subprocess.SubprocessError, OSError) as e:
        logger.debug("ffprobe duration failed for %s: %s", path, e)
    return None


def _has_audio_stream(path: str) -> bool:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (subprocess.SubprocessError, OSError):
        return False


def build_intro_concat_command(
    *,
    intro_path: str,
    body_path: str,
    output_path: str,
    intro_has_audio: bool,
    intro_duration: float,
) -> list[str]:
    """
    Concat intro then body; both scaled to 9:16. Silent audio on intro if missing.
    """
    scale = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},setsar=1,fps=30"
    )

    if intro_has_audio:
        audio_intro = "[0:a]aformat=sample_rates=48000:channel_layouts=stereo[a0]"
    else:
        dur = max(intro_duration, 0.1)
        audio_intro = (
            f"anullsrc=r=48000:cl=stereo,atrim=duration={dur:.3f}," f"asetpts=PTS-STARTPTS[a0]"
        )

    filter_complex = (
        f"[0:v]{scale},setpts=PTS-STARTPTS[v0];"
        f"[1:v]{scale},setpts=PTS-STARTPTS[v1];"
        f"{audio_intro};"
        f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo[a1];"
        f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]"
    )

    return [
        "ffmpeg",
        "-y",
        "-i",
        intro_path,
        "-i",
        body_path,
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        output_path,
    ]


def prepend_channel_intro(
    body_path: str,
    *,
    channel_id: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    Prepend intro to body_path. Returns final output path (overwrites body in place by default).
    """
    intro_path = resolve_intro_path(channel_id)
    if not intro_path:
        return body_path

    body_path = os.path.abspath(body_path)
    if not os.path.isfile(body_path):
        raise FileNotFoundError(body_path)

    final_path = os.path.abspath(output_path or body_path)
    work_body = body_path
    temp_body = ""
    if final_path == body_path:
        temp_body = body_path + ".body.tmp.mp4"
        work_body = temp_body
        from core.file_lock import retry_locked

        retry_locked(lambda: os.replace(body_path, temp_body))

    intro_dur = _probe_duration(intro_path)
    if intro_dur is None:  # not `or 3.0` — a real 0.0 is a probe answer, not a miss
        intro_dur = 3.0
    cmd = build_intro_concat_command(
        intro_path=intro_path,
        body_path=work_body,
        output_path=final_path,
        intro_has_audio=_has_audio_stream(intro_path),
        intro_duration=intro_dur,
    )

    logger.info("Prepending channel intro (%s)", os.path.basename(intro_path))
    concat_ok = False
    try:
        from core.file_lock import is_lock_error, lock_delay_sec, lock_retries

        process = None
        attempts = lock_retries()
        delay = lock_delay_sec()
        for i in range(attempts):
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode == 0:
                break
            err = process.stderr or ""
            if is_lock_error(None, err) and i < attempts - 1:
                logger.warning("Intro concat file-lock retry %s/%s", i + 1, attempts)
                import time as _time

                _time.sleep(delay * (i + 1))
                continue
            break
        if process is None or process.returncode != 0:
            raise RuntimeError(f"Intro concat failed: {(process.stderr if process else '')[-800:]}")
        # Exit 0 is not proof of an output: a truncated or empty file here would be
        # "successful" right up until we delete the temp holding the real render.
        if not os.path.isfile(final_path) or os.path.getsize(final_path) == 0:
            raise RuntimeError(f"Intro concat exited 0 but wrote no usable file: {final_path}")
        concat_ok = True
    finally:
        # From the os.replace above to here, the rendered video exists ONLY under the
        # temp name. Every exit from that window has to put it back — a non-zero exit,
        # ffmpeg missing from PATH (subprocess raises before there is an exit code),
        # an empty output, or a Ctrl-C. Otherwise render_vertical_video's
        # "Channel intro skipped (render kept)" is a lie and the pipeline stores an
        # mp4_path with no file behind it.
        if not concat_ok and temp_body and os.path.isfile(temp_body):
            os.replace(temp_body, body_path)

    if temp_body and os.path.isfile(temp_body):
        try:
            os.remove(temp_body)
        except OSError as e:
            logger.warning("Could not remove temp body %s: %s", temp_body, e)

    return final_path
