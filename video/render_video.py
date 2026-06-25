import os
import subprocess

from moviepy.editor import AudioFileClip

from assets.manager import get_background_asset
from core.logging import get_logger
from core.render_progress import (
    RenderProgress,
    ffmpeg_simple_run,
    is_render_progress_enabled,
    run_ffmpeg_with_progress,
)
from video.subtitles import generate_subtitle_file

logger = get_logger("video.render")

TARGET_W = 1080
TARGET_H = 1920


def _probe_video_duration(path: str) -> float | None:
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
        logger.debug("ffprobe duration failed: %s", e)
    return None


def _escape_subtitle_path(path: str) -> str:
    return path.replace("\\", "/").replace(":", r"\:")


def build_render_ffmpeg_command(
    *,
    background_path: str,
    mp3_path: str,
    output_path: str,
    subtitle_path: str,
    duration: float,
) -> list[str]:
    """
    FFmpeg command: loop background video only (no stock audio), TTS audio only,
    scale/crop to vertical, burn subtitles, fixed output duration.
    """
    subtitle_escaped = _escape_subtitle_path(subtitle_path)
    duration_str = f"{duration:.3f}"

    # Video-only filter graph from input 0; input 1 audio mapped explicitly.
    filter_complex = (
        f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},"
        f"setpts=PTS-STARTPTS,"
        f"subtitles='{subtitle_escaped}'[vout]"
    )

    return [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        background_path,
        "-i",
        mp3_path,
        "-t",
        duration_str,
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "1:a:0",
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


def render_vertical_video(
    mp3_path,
    topic,
    output_filename,
    script,
    channel_id=None,
    *,
    progress: RenderProgress | None = None,
):
    if progress is None and is_render_progress_enabled():
        progress = RenderProgress()

    def stage(msg: str) -> None:
        if progress:
            progress.stage(msg)
        else:
            logger.info(msg)

    stage("Loading audio (duration probe)...")
    audio_clip = AudioFileClip(mp3_path)
    duration = audio_clip.duration
    audio_clip.close()
    if progress:
        progress.note(f"Audio length: {duration:.1f}s")

    stage("Fetching background (hybrid/stock/local)...")
    # Scene-matched B-roll (opt-in): cut a clip per script beat. Falls back to the
    # normal single/hybrid background on any miss, so it never breaks the render.
    asset = None
    try:
        from assets.manager import get_scene_matched_background
        from core.tts import word_timing_path

        words = None
        sidecar = word_timing_path(mp3_path)
        if os.path.exists(sidecar):
            import json

            with open(sidecar, encoding="utf-8") as f:
                words = json.load(f)
        asset = get_scene_matched_background(
            topic, script, channel_id, duration=duration, words=words
        )
    except Exception:
        asset = None
    if asset is None:
        asset = get_background_asset(topic, channel_id, duration=duration)
    background_path = asset.path
    if progress:
        progress.note(f"Background: {asset.provider} — {os.path.basename(background_path)}")
    logger.info("Background provider=%s path=%s", asset.provider, background_path)
    if asset.attribution:
        logger.info("Attribution: %s", asset.attribution)

    bg_duration = _probe_video_duration(os.path.abspath(background_path))
    if bg_duration is not None and bg_duration < duration:
        if progress:
            progress.note(f"Looping background ({bg_duration:.1f}s → {duration:.1f}s)")
        logger.info(
            "Background %.1fs shorter than audio %.1fs — looping to fill",
            bg_duration,
            duration,
        )

    stage("Generating subtitles...")
    subtitle_path = generate_subtitle_file(script, duration, audio_path=mp3_path)

    audio_dir = os.path.dirname(os.path.abspath(mp3_path))
    video_dir = os.path.join(os.path.dirname(audio_dir), "video")
    os.makedirs(video_dir, exist_ok=True)
    output_path = os.path.join(video_dir, output_filename)

    background_path = os.path.abspath(background_path).replace("\\", "/")
    mp3_path = os.path.abspath(mp3_path).replace("\\", "/")
    subtitle_path = os.path.abspath(subtitle_path).replace("\\", "/")
    output_path = os.path.abspath(output_path).replace("\\", "/")

    cmd = build_render_ffmpeg_command(
        background_path=background_path,
        mp3_path=mp3_path,
        output_path=output_path,
        subtitle_path=subtitle_path,
        duration=duration,
    )

    stage(f"FFmpeg render (~{duration:.0f}s video)...")
    if progress and progress.enabled:
        progress.note(
            "Typical encode: 2-6 min for ~2 min video. "
            "Set FFMPEG_SIMPLE_RUN=true if progress stalls."
        )

    use_progress = progress and progress.enabled and not ffmpeg_simple_run()
    if use_progress:
        process = run_ffmpeg_with_progress(cmd, duration_sec=duration, progress=progress)
    else:
        logger.info(
            "Rendering with FFmpeg (loop bg, mute stock audio, duration=%ss)",
            f"{duration:.3f}",
        )
        process = subprocess.run(cmd, capture_output=True, text=True)

    if process.returncode != 0:
        logger.error("FFmpeg failed: %s", (process.stderr or "")[-1200:])
        raise Exception("FFmpeg render failed.")

    from video.channel_intro import prepend_channel_intro, resolve_intro_path

    if resolve_intro_path(channel_id):
        stage("Prepending channel intro...")
        try:
            prepend_channel_intro(output_path, channel_id=channel_id)
            if progress:
                progress.note("Channel intro prepended")
        except Exception as e:
            logger.warning("Channel intro skipped (render kept): %s", e)
            if progress:
                progress.note(f"Intro skipped: {e}")

    if progress:
        progress.done(f"Video saved: {output_path}")
    logger.info("Video saved: %s", output_path)
    return output_path, asset
