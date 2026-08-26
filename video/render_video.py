import os
import subprocess
from collections.abc import Callable

from moviepy.editor import AudioFileClip

from assets.manager import get_background_asset
from core.logging import get_logger
from core.render_progress import (
    RenderProgress,
    ffmpeg_simple_run,
    is_render_progress_enabled,
    run_ffmpeg_with_progress,
)
from video.subtitles import caption_force_style, caption_style, generate_subtitle_file

logger = get_logger("video.render")


def _ffmpeg_run(cmd, *, duration_sec=None, progress=None, use_progress=False):
    """Run ffmpeg, retrying Windows file-lock (Defender) errors."""
    import time as _time

    from core.file_lock import is_lock_error, lock_delay_sec, lock_retries

    attempts = lock_retries()
    delay = lock_delay_sec()
    process = None
    for i in range(attempts):
        if use_progress and progress is not None:
            process = run_ffmpeg_with_progress(cmd, duration_sec=duration_sec, progress=progress)
        else:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        if process.returncode == 0:
            return process
        err = process.stderr or ""
        if is_lock_error(None, err) and i < attempts - 1:
            logger.warning("FFmpeg file-lock retry %s/%s", i + 1, attempts)
            _time.sleep(delay * (i + 1))
            continue
        return process
    return process


TARGET_W = 1080
TARGET_H = 1920

# Music bed duck level: the bed is scaled to this gain and mixed under the VO with
# amix normalize=0, which keeps the VO at unit gain (dominant) — see
# build_render_ffmpeg_command.
MUSIC_BED_VOLUME = 0.2


def _loudnorm_enabled() -> bool:
    return os.getenv("LUFS_NORMALIZE", "").strip().lower() in ("1", "true", "yes", "on")


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


def _resolve_color_grade(channel_id: str | None) -> dict[str, float] | None:
    try:
        from config.channels import get_channel_profile

        raw = dict(get_channel_profile(channel_id).color_grade or {})
        if not raw:
            return None
        grade = {
            "saturation": float(raw.get("saturation", 1.0)),
            "contrast": float(raw.get("contrast", 1.0)),
            "brightness": float(raw.get("brightness", 0.0)),
        }
        if not (
            0.5 <= grade["saturation"] <= 2.0
            and 0.5 <= grade["contrast"] <= 2.0
            and -0.3 <= grade["brightness"] <= 0.3
        ):
            raise ValueError("values outside validated bounds")
        return grade
    except Exception as exc:
        logger.warning("Color grade skipped for channel=%s: %s", channel_id, exc)
        return None


def build_render_ffmpeg_command(
    *,
    background_path: str,
    mp3_path: str,
    output_path: str,
    subtitle_path: str,
    duration: float,
    profile=None,
    music_path: str | None = None,
    caption_force_style: str = "",
    render_preset: str = "publish",
    lower_thirds_path: str | None = None,
    color_grade: dict[str, float] | None = None,
    hook_motion_filter: str = "",
) -> list[str]:
    """
    FFmpeg command: loop background video only (no stock audio), TTS audio only,
    scale/crop to the profile's aspect (vertical 9:16 by default), burn subtitles,
    fixed output duration. `profile` is a video.render_profiles.RenderProfile; None
    keeps the current vertical 1080x1920 output byte-identical.

    `music_path` (Pillar 6 music bed) adds a looped third input mixed UNDER the VO:
    the bed is ducked to MUSIC_BED_VOLUME while `amix ... normalize=0` leaves the VO
    at unit gain, so the voice stays dominant. `music_path=None` emits a command
    byte-identical to the VO-only command of today.
    """
    is_draft = str(render_preset).strip().lower() == "draft"
    width = 480 if is_draft else (profile.width if profile is not None else TARGET_W)
    height = 854 if is_draft else (profile.height if profile is not None else TARGET_H)
    encoder_preset = "ultrafast" if is_draft else "fast"
    crf = "30" if is_draft else "23"
    subtitle_escaped = _escape_subtitle_path(subtitle_path)
    style_escaped = caption_force_style.replace("'", r"\'")
    lower_thirds_escaped = _escape_subtitle_path(lower_thirds_path) if lower_thirds_path else ""
    duration_str = f"{duration:.3f}"
    grade_filter = ""
    if color_grade and any(
        (
            float(color_grade["saturation"]) != 1.0,
            float(color_grade["contrast"]) != 1.0,
            float(color_grade["brightness"]) != 0.0,
        )
    ):
        grade_filter = (
            f"eq=saturation={float(color_grade['saturation']):.4f}:"
            f"contrast={float(color_grade['contrast']):.4f}:"
            f"brightness={float(color_grade['brightness']):.4f},"
        )
    motion_filter = (
        hook_motion_filter.format(width=width, height=height) + "," if hook_motion_filter else ""
    )

    # Video-only filter graph from input 0; input 1 audio mapped explicitly.
    filter_complex = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"{grade_filter}"
        f"{motion_filter}"
        f"setpts=PTS-STARTPTS,"
        f"{f'subtitles={lower_thirds_escaped!r},' if lower_thirds_escaped else ''}"
        f"subtitles='{subtitle_escaped}'"
        f"{f':force_style={style_escaped!r}' if style_escaped else ''}[vout]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        background_path,
        "-i",
        mp3_path,
    ]
    audio_map = "1:a:0"
    if music_path is not None:
        # Loop the bed (input 2) so a short bed still covers the full VO; duck it and
        # mix under the VO. duration=first ends the mix with the VO, and -t below
        # bounds the output either way.
        cmd += ["-stream_loop", "-1", "-i", music_path]
        filter_complex += (
            f";[2:a]volume={MUSIC_BED_VOLUME}[bed];"
            f"[1:a][bed]amix=inputs=2:duration=first:normalize=0[aout]"
        )
        audio_map = "[aout]"
        if _loudnorm_enabled():
            filter_complex += ";[aout]loudnorm=I=-14:TP=-1.5:LRA=11[anorm]"
            audio_map = "[anorm]"
    elif _loudnorm_enabled():
        filter_complex += ";[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
        audio_map = "[aout]"
    cmd += [
        "-t",
        duration_str,
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        audio_map,
        "-c:v",
        "libx264",
        "-preset",
        encoder_preset,
        "-crf",
        crf,
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        output_path,
    ]
    return cmd


def _resolve_music_bed(duration: float, stage) -> str | None:
    """Music bed path when MUSIC_PROVIDER delivers one, else None (Pillar 6, fail-open).

    Any miss — gate unset, backend not installed, generation error, missing file —
    returns None so the caller renders VO-only exactly as today. Never raises.
    """
    if (os.getenv("MUSIC_PROVIDER") or "none").strip().lower() in ("", "none"):
        return None
    try:
        from core.music import generate_bed

        mood = (os.getenv("MUSIC_MOOD") or "").strip() or "upbeat"
        stage("Generating music bed...")
        result = generate_bed(mood, duration)
        if result.ok and result.data and os.path.isfile(str(result.data)):
            return os.path.abspath(str(result.data)).replace("\\", "/")
        logger.info("Music bed unavailable (VO-only): %s", result.detail or result.status)
    except Exception as exc:
        logger.warning("Music bed skipped (VO-only): %s", exc)
    return None


def render_vertical_video(
    mp3_path,
    topic,
    output_filename,
    script,
    channel_id=None,
    *,
    progress: RenderProgress | None = None,
    command_callback: Callable[[str, list[str]], None] | None = None,
    render_preset: str = "publish",
    lower_thirds: list[str] | None = None,
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

    audio_dir = os.path.dirname(os.path.abspath(mp3_path))
    video_dir = os.path.join(os.path.dirname(audio_dir), "video")
    os.makedirs(video_dir, exist_ok=True)
    output_path = os.path.join(video_dir, output_filename)
    subtitle_ext = ".ass" if caption_style(channel_id) == "karaoke" else ".srt"
    stable_subtitle = os.path.splitext(output_path)[0] + subtitle_ext

    stage("Generating subtitles...")
    subtitle_path = generate_subtitle_file(
        script,
        duration,
        audio_path=mp3_path,
        channel_id=channel_id,
        output_path=stable_subtitle,
    )
    from video.subtitles import _load_word_timings

    word_timings = _load_word_timings(mp3_path)
    lower_thirds_path: str | None = None
    if lower_thirds:
        try:
            from video.lower_thirds import build_lower_thirds_ass

            lower_text = build_lower_thirds_ass(lower_thirds, word_timings)
            if lower_text:
                lower_thirds_path = os.path.splitext(output_path)[0] + ".lower_thirds.ass"
                with open(lower_thirds_path, "w", encoding="utf-8") as handle:
                    handle.write(lower_text)
                if progress:
                    progress.note(f"Lower thirds: {len(lower_thirds)} grounded label(s)")
            elif progress:
                progress.note("Lower thirds skipped: no real matching word timings")
        except Exception as exc:
            logger.warning("Lower thirds skipped: %s", exc)

    background_path = os.path.abspath(background_path).replace("\\", "/")
    mp3_path = os.path.abspath(mp3_path).replace("\\", "/")
    subtitle_path = os.path.abspath(subtitle_path).replace("\\", "/")
    if lower_thirds_path:
        lower_thirds_path = os.path.abspath(lower_thirds_path).replace("\\", "/")
    output_path = os.path.abspath(output_path).replace("\\", "/")

    try:
        from core.disk_preflight import block_reason as disk_block

        why = disk_block(output_path)
        if why:
            raise RuntimeError(why)
    except RuntimeError:
        raise
    except Exception as exc:
        logger.debug("disk preflight skipped: %s", exc)

    # Music bed (Pillar 6): mixed under the VO when MUSIC_PROVIDER delivers; any miss
    # keeps music_path None and the command below byte-identical to the VO-only render.
    music_path = _resolve_music_bed(duration, stage)
    color_grade = _resolve_color_grade(channel_id)
    hook_motion_filter = ""
    try:
        from config.channels import get_channel_profile
        from video.hook_motion import first_caption_motion_filter

        hook_motion_filter = first_caption_motion_filter(
            word_timings, get_channel_profile(channel_id).hook_motion
        )
        if get_channel_profile(channel_id).hook_motion and not hook_motion_filter and progress:
            progress.note("Hook motion skipped: no real first-cue timing")
    except Exception as exc:
        logger.warning("Hook motion skipped for channel=%s: %s", channel_id, exc)

    cmd = build_render_ffmpeg_command(
        background_path=background_path,
        mp3_path=mp3_path,
        output_path=output_path,
        subtitle_path=subtitle_path,
        duration=duration,
        music_path=music_path,
        caption_force_style=caption_force_style(channel_id),
        render_preset=render_preset,
        lower_thirds_path=lower_thirds_path,
        color_grade=color_grade,
        hook_motion_filter=hook_motion_filter,
    )
    if command_callback is not None:
        try:
            command_callback("primary_attempt", list(cmd))
        except Exception as exc:
            logger.debug("render attempt capture skipped: %s", exc)

    stage(f"FFmpeg render (~{duration:.0f}s video)...")
    if progress and progress.enabled:
        progress.note(
            "Typical encode: 2-6 min for ~2 min video. "
            "Set FFMPEG_SIMPLE_RUN=true if progress stalls."
        )

    use_progress = progress and progress.enabled and not ffmpeg_simple_run()
    if not use_progress:
        logger.info(
            "Rendering with FFmpeg (loop bg, mute stock audio, duration=%ss)",
            f"{duration:.3f}",
        )
    process = _ffmpeg_run(
        cmd, duration_sec=duration, progress=progress, use_progress=bool(use_progress)
    )

    if process.returncode != 0 and music_path is not None:
        # The music bed must never break a render: drop it and retry VO-only once
        # with the exact command used before the bed existed.
        logger.warning(
            "FFmpeg failed with music bed - retrying VO-only: %s",
            (process.stderr or "")[-400:],
        )
        stage("Music mix failed - retrying VO-only...")
        music_path = None
        cmd = build_render_ffmpeg_command(
            background_path=background_path,
            mp3_path=mp3_path,
            output_path=output_path,
            subtitle_path=subtitle_path,
            duration=duration,
            caption_force_style=caption_force_style(channel_id),
            render_preset=render_preset,
            lower_thirds_path=lower_thirds_path,
            color_grade=color_grade,
            hook_motion_filter=hook_motion_filter,
        )
        if command_callback is not None:
            try:
                command_callback("primary_attempt", list(cmd))
            except Exception as exc:
                logger.debug("fallback attempt capture skipped: %s", exc)
        process = _ffmpeg_run(cmd)

    if process.returncode != 0:
        logger.error("FFmpeg failed: %s", (process.stderr or "")[-1200:])
        raise Exception("FFmpeg render failed.")
    if command_callback is not None:
        try:
            command_callback("primary_success", list(cmd))
        except Exception as exc:
            logger.debug("render success capture skipped: %s", exc)

    from video.channel_intro import prepend_channel_intro, resolve_intro_path

    if render_preset != "draft" and resolve_intro_path(channel_id):
        stage("Prepending channel intro...")
        try:
            prepend_channel_intro(
                output_path,
                channel_id=channel_id,
                command_callback=command_callback,
            )
            if progress:
                progress.note("Channel intro prepended")
        except Exception as e:
            logger.warning("Channel intro skipped (render kept): %s", e)
            if progress:
                progress.note(f"Intro skipped: {e}")

    if render_preset != "draft":
        from video.channel_outro import append_channel_outro, resolve_end_card

        if resolve_end_card(channel_id):
            stage("Appending generated end card...")
            try:
                append_channel_outro(
                    output_path,
                    channel_id=channel_id,
                    command_callback=command_callback,
                )
                if progress:
                    progress.note("End card appended")
            except Exception as exc:
                logger.warning("End card skipped (render kept): %s", exc)
                if progress:
                    progress.note(f"End card skipped: {exc}")

    # Dual-format reach (Pillar 6): the primary 9:16 output above is untouched. When
    # RENDER_FORMATS names extra aspects, emit those cuts too (same bg/VO/captions),
    # each fail-open so a bonus cut can never break the primary render.
    if render_preset != "draft":
        _render_extra_formats(
            background_path=background_path,
            mp3_path=mp3_path,
            primary_output=output_path,
            subtitle_path=subtitle_path,
            duration=duration,
            stage=stage,
            music_path=music_path,
            lower_thirds_path=lower_thirds_path,
            color_grade=color_grade,
            hook_motion_filter=hook_motion_filter,
        )

    if progress:
        progress.done(f"Video saved: {output_path}")
    logger.info("Video saved: %s", output_path)
    return output_path, asset


def _render_extra_formats(
    *,
    background_path: str,
    mp3_path: str,
    primary_output: str,
    subtitle_path: str,
    duration: float,
    stage,
    music_path: str | None = None,
    lower_thirds_path: str | None = None,
    color_grade: dict[str, float] | None = None,
    hook_motion_filter: str = "",
) -> list[str]:
    """Render each non-vertical RENDER_FORMATS profile as a suffixed sibling file.

    Returns the list of extra output paths written. Fully fail-open: any failure is
    logged and skipped — the primary vertical render is already complete and returned.
    `music_path` mirrors the primary render's audio mix (same bed, or None for VO-only).
    """
    try:
        from video.render_profiles import extra_profiles

        extras = extra_profiles()
    except Exception:
        return []
    if not extras:
        return []

    stem, ext = os.path.splitext(primary_output)
    written: list[str] = []
    for profile in extras:
        alt_output = f"{stem}{profile.suffix}{ext}"
        try:
            cmd = build_render_ffmpeg_command(
                background_path=background_path,
                mp3_path=mp3_path,
                output_path=alt_output,
                subtitle_path=subtitle_path,
                duration=duration,
                profile=profile,
                music_path=music_path,
                lower_thirds_path=lower_thirds_path,
                color_grade=color_grade,
                hook_motion_filter=hook_motion_filter,
            )
            stage(f"Extra format: {profile.name} ({profile.width}x{profile.height})...")
            proc = _ffmpeg_run(cmd)
            if proc.returncode == 0 and os.path.isfile(alt_output):
                written.append(alt_output)
                logger.info("Extra-format render saved: %s", alt_output)
            else:
                logger.warning(
                    "Extra-format render %s failed (kept primary): %s",
                    profile.name,
                    (proc.stderr or "")[-400:],
                )
        except Exception as exc:
            logger.warning("Extra-format render %s skipped: %s", profile.name, exc)
    return written
