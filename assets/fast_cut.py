"""Fast-cut backgrounds: a new shot every 2-3 seconds (#782).

Operator, 2026-09-18, rejecting three drafts: "the clips need to be much shorter, idk like the
other videos do. more clips per, less time in each." A hybrid background was one local clip then
one stock clip for the whole video, so a 55 s Short held each shot for ~25 s.

This cuts the background into shots of about `BACKGROUND_CUT_SECONDS` (default 2.5, each shot
kept between 0.8x and 1.2x of it), landing each cut on the end of a phrase when the voice has
word timings (the ElevenLabs sidecar, or the aligned one from #771), else on an even rhythm.
Shots come from the game folder the topic picks (`LocalAssetProvider.candidate_clips`), never
the same clip twice in a row, each from a random point inside the clip.

Each shot is rendered to its own small file with fixed encoder settings, then the shots are
joined with ffmpeg's concat demuxer as a stream copy. That keeps a 120-shot long video from
opening 120 decoders at once, and identical settings are what make a stream copy safe.

    BACKGROUND_FAST_CUT=true      # default; false = the old two-shot hybrid
    BACKGROUND_CUT_SECONDS=2.5
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
import uuid
from typing import Any

from core.logging import get_logger

logger = get_logger("assets.fast_cut")

TARGET_W = 1080
TARGET_H = 1920
_DEFAULT_CUT = 2.5
_MIN_POOL = 3
_MAX_POOL = 12
_PHRASE_END = tuple(",.!?;:")
# Fixed, not the NVENC helper: the concat stream copy needs every shot encoded identically.
_SHOT_ENCODER = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "30"]


def fast_cut_enabled() -> bool:
    raw = (os.getenv("BACKGROUND_FAST_CUT", "") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


def cut_seconds() -> float:
    try:
        value = float(os.getenv("BACKGROUND_CUT_SECONDS", "") or _DEFAULT_CUT)
    except ValueError:
        value = _DEFAULT_CUT
    return min(8.0, max(1.0, value))


def _word_ends(words: list[dict[str, Any]] | None) -> tuple[list[float], list[float]]:
    """(phrase ends, all word ends) from a word-timing sidecar."""
    phrase: list[float] = []
    every: list[float] = []
    for row in words or []:
        if not isinstance(row, dict) or not isinstance(row.get("end"), int | float):
            continue
        end = float(row["end"])
        every.append(end)
        if str(row.get("word") or "").rstrip().endswith(_PHRASE_END):
            phrase.append(end)
    return phrase, every


def cut_points(
    duration: float,
    words: list[dict[str, Any]] | None = None,
    *,
    target: float | None = None,
) -> list[float]:
    """Shot boundaries from 0 to `duration`, each shot `lo`..`hi` seconds long."""
    duration = float(duration or 0.0)
    if duration <= 0:
        return [0.0]
    target = float(target or cut_seconds())
    lo, hi = target * 0.8, target * 1.2
    if duration <= hi:
        return [0.0, duration]
    phrase_ends, word_ends = _word_ends(words)

    def _pick(t: float) -> float:
        start, stop = t + lo, t + hi
        for pool in (phrase_ends, word_ends):
            inside = [e for e in pool if start <= e <= stop]
            if inside:
                return min(inside, key=lambda e: abs(e - (t + target)))
        return t + target

    bounds = [0.0]
    while duration - bounds[-1] > hi:
        bounds.append(round(_pick(bounds[-1]), 3))
    # The tail is under `hi`. If it is also under `lo`, split the last two shots evenly
    # instead of leaving a blink of a shot at the end.
    if duration - bounds[-1] < lo and len(bounds) >= 2:
        bounds[-1] = round((bounds[-2] + duration) / 2, 3)
    bounds.append(duration)
    return bounds


def plan_shots(
    bounds: list[float],
    clips: list[str],
    *,
    durations: dict[str, float] | None = None,
    rng: random.Random | None = None,
) -> list[tuple[str, float, float]]:
    """(clip, in-point, length) per shot: the pool in rotation, never a clip twice in a row."""
    rng = rng or random.Random()
    pool = list(dict.fromkeys(c for c in clips if c))
    if not pool:
        return []
    order: list[str] = []
    shots: list[tuple[str, float, float]] = []
    for a, b in zip(bounds, bounds[1:], strict=False):
        length = max(0.1, b - a)
        if not order:
            order = pool[:]
            rng.shuffle(order)
            if shots and len(order) > 1 and order[0] == shots[-1][0]:
                order.append(order.pop(0))
        clip = order.pop(0)
        clip_len = (durations or {}).get(clip)
        room = (float(clip_len) - length) if clip_len else 0.0
        start = round(rng.uniform(0.0, room), 3) if room > 0.2 else 0.0
        shots.append((clip, start, round(length, 3)))
    return shots


def build_shot_command(clip: str, start: float, length: float, output: str) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{length:.3f}",
        "-i",
        clip,
        "-vf",
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},fps=30,format=yuv420p,setpts=PTS-STARTPTS",
        *_SHOT_ENCODER,
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-an",
        output,
    ]


def build_concat_command(list_path: str, output: str, duration: float) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_path,
        "-t",
        f"{duration:.3f}",
        "-c",
        "copy",
        "-an",
        output,
    ]


def _probe(path: str) -> float | None:
    try:
        from video.channel_intro import _probe_duration

        return _probe_duration(path)
    except Exception:
        return None


def _clip_pool(topic: str, channel_id: str | None) -> list[str]:
    from assets.category import detect_category
    from assets.local_provider import LocalAssetProvider

    clips = LocalAssetProvider().candidate_clips(topic, detect_category(topic), channel_id)
    try:
        from assets.clip_memory import recent

        seen = set(recent())
        clips.sort(key=lambda c: os.path.normcase(os.path.abspath(c)) in seen)
    except Exception as exc:
        logger.debug("clip memory ordering skipped: %s", exc)
    return clips[:_MAX_POOL]


def try_fast_cut_background(
    topic: str,
    channel_id: str | None,
    *,
    duration: float,
    words: list[dict[str, Any]] | None = None,
):
    """A fast-cut background as an AssetResult, or None to keep the old path. Never raises."""
    if not fast_cut_enabled() or not duration or duration <= 0:
        return None
    try:
        pool = _clip_pool(topic, channel_id)
    except Exception as exc:
        logger.debug("fast cut: clip pool unavailable: %s", exc)
        return None
    if len(pool) < _MIN_POOL:
        logger.info(
            "fast cut: only %d clip(s) for '%s' - keeping the old background", len(pool), topic
        )
        return None
    try:
        return _compose(pool, topic, float(duration), words)
    except Exception as exc:
        logger.warning("fast cut failed; keeping the old background: %s", exc)
        return None


def _compose(pool: list[str], topic: str, duration: float, words):
    from assets.types import AssetResult
    from config.paths import DATA_DIR, ensure_data_dir

    durations = {clip: d for clip in pool if (d := _probe(clip))}
    shots = plan_shots(cut_points(duration, words), pool, durations=durations)
    ensure_data_dir()
    out_dir = os.path.join(DATA_DIR, "tmp", "hybrid_backgrounds")
    os.makedirs(out_dir, exist_ok=True)
    output = os.path.join(out_dir, f"fastcut_{uuid.uuid4().hex[:12]}.mp4")
    work = tempfile.mkdtemp(prefix="fastcut_")
    try:
        lines = []
        for i, (clip, start, length) in enumerate(shots):
            shot = os.path.join(work, f"shot_{i:04d}.mp4")
            proc = subprocess.run(
                build_shot_command(os.path.abspath(clip), start, length, shot),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0 or not os.path.isfile(shot):
                raise RuntimeError(f"shot {i} from {clip}: {(proc.stderr or '')[-300:]}")
            lines.append(f"file '{shot.replace(os.sep, '/')}'")
        list_path = os.path.join(work, "shots.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        proc = subprocess.run(
            build_concat_command(list_path, output, duration),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0 or not os.path.isfile(output):
            raise RuntimeError(f"concat: {(proc.stderr or '')[-300:]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    try:
        from assets.clip_memory import record

        for clip in dict.fromkeys(c for c, _s, _l in shots):
            record(clip)
    except Exception as exc:
        logger.debug("clip memory record skipped: %s", exc)
    logger.info("fast cut: %d shots from %d clips (%s)", len(shots), len(set(pool)), topic)
    return AssetResult(
        path=output,
        provider="fast_cut",
        query=topic,
        attribution=f"Gameplay (local), {len(shots)} shots",
    )


def render_preview(
    audio_path: str,
    topic: str,
    channel_id: str | None = None,
    *,
    out_dir: str | None = None,
) -> str:
    """Render an existing voiced Short again with today's background, at no voice cost.

    Works on a copy: `render_vertical_video` edits its mp3 in place (hook pause), and the
    original belongs to a real run. The script comes from the word-timing sidecar.
    """
    import json

    from core.output_paths import channel_output_root
    from video.render_video import render_vertical_video

    out_dir = out_dir or os.path.join(channel_output_root(channel_id), "preview")
    # The render writes to <audio dir>/../video, so the copy sits in preview/audio and the
    # result lands in preview/video - never beside the real renders.
    audio_dir = os.path.join(out_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    stem = f"preview_{uuid.uuid4().hex[:8]}"
    copy = os.path.join(audio_dir, f"{stem}.mp3")
    shutil.copyfile(audio_path, copy)
    sidecar = audio_path + ".words.json"
    script = ""
    if os.path.isfile(sidecar):
        shutil.copyfile(sidecar, copy + ".words.json")
        with open(sidecar, encoding="utf-8") as f:
            script = " ".join(str(w.get("word") or "") for w in json.load(f) if isinstance(w, dict))
    # A bare filename: render_vertical_video joins it under its own video folder and returns
    # the real path (a full path here nested it: video/output/tapin/preview/...).
    output, _background = render_vertical_video(
        copy, topic, f"{stem}.mp4", script.strip() or topic, channel_id
    )
    return str(output)
