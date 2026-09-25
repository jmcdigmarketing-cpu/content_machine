"""Fast-cut backgrounds: a new footage shot every few seconds (#782, #792).

Operator, 2026-09-18, rejecting three drafts: "the clips need to be much shorter, idk like the
other videos do. more clips per, less time in each." A hybrid background was one local clip then
one stock clip for the whole video, so a 55 s Short held each shot for ~25 s.

Each shot runs 3-8 s (#792), drawn at random and never within a second of the shot before it,
so the pacing does not settle into a beat - the operator reversed wave 22's steady ~2.5 s
rhythm after watching it: "can it be a bit longer cuts? like between the 3-8s range? ... dont
cut consistiently tbh reverse that decision." Each cut still lands on the end of a phrase when
the voice has word timings (the ElevenLabs sidecar, or the aligned one from #771).
Shots come from the game folder the topic picks (`LocalAssetProvider.candidate_clips`), never
the same clip twice in a row, each from a random point inside the clip.

Each shot is rendered to its own small file with fixed encoder settings, then the shots are
joined with ffmpeg's concat demuxer as a stream copy. That keeps a 120-shot long video from
opening 120 decoders at once, and identical settings are what make a stream copy safe.

    BACKGROUND_FAST_CUT=true      # default; false = the old two-shot hybrid
    BACKGROUND_CUT_MIN=3          # shortest shot
    BACKGROUND_CUT_MAX=8          # longest shot
    BACKGROUND_CROP_BOTTOM=0.18   # share of the game frame's bottom cropped away (#785)

The game's own text - GTA mission lines, subtitles, the HUD strip - sits in the bottom band of
the source frame. Operator, 2026-09-19: "dont skip those clips, crop it out". Every shot drops
that band before it is scaled, so the clip stays in the pool and the text never reaches the
caption area.

A long gameplay file (a 20-minute download) counts as one window per 30 s of footage, so a
single file can carry a whole Short with shots from all over it.
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from core.logging import get_logger

logger = get_logger("assets.fast_cut")

TARGET_W = 1080
TARGET_H = 1920
_DEFAULT_MIN = 3.0
_DEFAULT_MAX = 8.0
# Two shots closer than this in length read as a rhythm, which is what the operator rejected.
_LENGTH_GAP = 1.0
_DEFAULT_WORKERS = 4
_MIN_POOL = 3
_MAX_POOL = 12
_WINDOW_SECONDS = 30.0
_DEFAULT_CROP = 0.18
# Mean luma (0-255) of the ungraded shot. GTA night driving measures 26-40 and the render's
# grade then takes it under 28 - near-black on a phone. Measured on the wave 23 preview.
_MIN_LUMA = 45.0
_DARK_REDRAWS = 2
# Composed backgrounds are scratch: the render copies what it needs. Wave 22 never swept them
# and data/tmp/hybrid_backgrounds reached 4.2 GB over three months (#797).
_KEEP_TMP_DAYS = 3
_PHRASE_END = tuple(",.!?;:")
# Fixed, not the NVENC helper: the concat stream copy needs every shot encoded identically.
_SHOT_ENCODER = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "30"]


def fast_cut_enabled() -> bool:
    raw = (os.getenv("BACKGROUND_FAST_CUT", "") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _env_float(key: str) -> float | None:
    raw = (os.getenv(key, "") or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def shot_workers() -> int:
    """How many shots encode at once (#796). ffmpeg is the CPU user, so a few is plenty."""
    value = _env_float("BACKGROUND_SHOT_WORKERS")
    if value is None:
        return _DEFAULT_WORKERS
    return max(1, min(16, int(value)))


def cut_range() -> tuple[float, float]:
    """(shortest, longest) shot in seconds. Wave 22's BACKGROUND_CUT_SECONDS is the midpoint."""
    lo = _env_float("BACKGROUND_CUT_MIN")
    hi = _env_float("BACKGROUND_CUT_MAX")
    if lo is None and hi is None:
        legacy = _env_float("BACKGROUND_CUT_SECONDS")
        if legacy:
            lo, hi = legacy - 2.5, legacy + 2.5
    lo = _DEFAULT_MIN if lo is None else lo
    hi = _DEFAULT_MAX if hi is None else hi
    lo, hi = min(lo, hi), max(lo, hi)
    return max(0.5, lo), min(30.0, max(hi, lo + 0.5))


def crop_bottom() -> float:
    """Share of the source frame's height cut from the bottom, 0-0.4 (#785)."""
    raw = (os.getenv("BACKGROUND_CROP_BOTTOM", "") or "").strip()
    try:
        value = float(raw) if raw else _DEFAULT_CROP
    except ValueError:
        value = _DEFAULT_CROP
    return min(0.4, max(0.0, value))


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


def _split_tail(pair: float, before: float | None, lo: float, hi: float) -> float:
    """Where to cut a leftover `pair` of seconds into two shots.

    Not in half: two equal shots are the beat the operator rejected, and the first half also
    has to stay clear of the shot before it. Both halves stay inside [lo, hi].
    """
    low = max(lo, pair - hi)
    high = min(hi, pair - lo)
    if high <= low:
        return max(lo, min(hi, pair / 2))
    best, best_score = low, -1.0
    steps = int((high - low) / 0.05) + 1
    for i in range(steps):
        first = low + i * 0.05
        score = min(
            abs(pair - 2 * first),
            abs(first - before) if before is not None else float("inf"),
        )
        if score > best_score:
            best, best_score = first, score
    return best


def cut_points(
    duration: float,
    words: list[dict[str, Any]] | None = None,
    *,
    span: tuple[float, float] | None = None,
    rng: random.Random | None = None,
) -> list[float]:
    """Shot boundaries from 0 to `duration`, each shot 3-8 s and unlike the one before it."""
    duration = float(duration or 0.0)
    if duration <= 0:
        return [0.0]
    lo, hi = span or cut_range()
    if duration <= hi:
        return [0.0, duration]
    rng = rng or random.Random()
    phrase_ends, word_ends = _word_ends(words)

    def _boundary(start: float, length: float) -> float:
        """The phrase (then word) end nearest `start + length`, inside the shot's own range."""
        first, last = start + lo, start + hi
        window_lo = max(first, start + length - _LENGTH_GAP)
        window_hi = min(last, start + length + _LENGTH_GAP)
        for pool in (phrase_ends, word_ends):
            inside = [e for e in pool if window_lo <= e <= window_hi]
            if inside:
                return round(float(min(inside, key=lambda e: abs(e - (start + length)))), 3)
        return round(start + length, 3)

    bounds = [0.0]
    previous: float | None = None
    while duration - bounds[-1] > hi:
        start = bounds[-1]
        length = rng.uniform(lo, hi)
        for _ in range(8):
            if previous is None or abs(length - previous) >= _LENGTH_GAP + 0.2:
                break
            length = rng.uniform(lo, hi)
        cut = _boundary(start, length)
        if previous is not None and abs(cut - start - previous) < _LENGTH_GAP:
            # The snap pulled this shot back onto the last one's length: step away from it.
            want = previous + _LENGTH_GAP if previous + _LENGTH_GAP <= hi else previous - _LENGTH_GAP
            retry = _boundary(start, want)
            cut = retry if abs(retry - start - previous) >= _LENGTH_GAP else round(start + want, 3)
        previous = float(cut) - start
        bounds.append(cut)
    tail = duration - bounds[-1]
    if lo <= tail <= hi and previous is not None and abs(tail - previous) < _LENGTH_GAP:
        # The last shot landed on the length of the one before it: move the boundary. When
        # what is left is close to 2x hi both halves are forced near hi, and no shift exists.
        before = (bounds[-2] - bounds[-3]) if len(bounds) >= 3 else None
        for shift in (-_LENGTH_GAP, _LENGTH_GAP):
            moved = previous + shift
            if not (lo <= moved <= hi and lo <= tail - shift <= hi):
                continue
            # Moving this boundary changes the shot before it too - do not fix one beat by
            # creating another.
            if before is not None and abs(moved - before) < _LENGTH_GAP:
                continue
            bounds[-1] = round(bounds[-1] + shift, 3)
            tail = duration - bounds[-1]
            break
    if tail < lo and len(bounds) >= 2:
        # Too short to stand alone: give it to the shot before, or split the pair evenly.
        if (duration - bounds[-2]) <= hi:
            bounds.pop()
        else:
            pair = duration - bounds[-2]
            before = (bounds[-2] - bounds[-3]) if len(bounds) >= 3 else None
            bounds[-1] = round(bounds[-2] + _split_tail(pair, before, lo, hi), 3)
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


def expand_pool(
    clips: list[str], durations: dict[str, float] | None
) -> tuple[list[str], dict[str, tuple[str, float, float | None]]]:
    """Split long clips into 30 s windows: (keys, key -> (clip, offset, window length)).

    A clip shorter than two windows, or one that could not be probed, is a single window
    keyed by its own path.
    """
    keys: list[str] = []
    windows: dict[str, tuple[str, float, float | None]] = {}
    for clip in dict.fromkeys(c for c in clips if c):
        length = (durations or {}).get(clip)
        count = int(float(length) // _WINDOW_SECONDS) if length else 0
        if count < 2:
            keys.append(clip)
            windows[clip] = (clip, 0.0, float(length) if length else None)
            continue
        for k in range(count):
            key = f"{clip}#{k}"
            keys.append(key)
            windows[key] = (clip, k * _WINDOW_SECONDS, _WINDOW_SECONDS)
    return keys, windows


def plan_windowed_shots(
    bounds: list[float],
    keys: list[str],
    windows: dict[str, tuple[str, float, float | None]],
    *,
    rng: random.Random | None = None,
) -> list[tuple[str, float, float]]:
    """`plan_shots` over windows, mapped back to (clip, in-point in the clip, length).

    In-points come from the first half of each window, so two neighbouring windows of one
    long file never start their shots less than half a window (15 s) apart.
    """
    longest = max((b - a for a, b in zip(bounds, bounds[1:], strict=False)), default=0.0)
    lengths = {
        k: (w[2] / 2 + longest if k != w[0] else w[2]) for k, w in windows.items() if w[2]
    }
    planned = plan_shots(bounds, keys, durations=lengths, rng=rng)
    return [
        (windows[key][0], round(windows[key][1] + start, 3), length)
        for key, start, length in planned
    ]


def build_shot_command(clip: str, start: float, length: float, output: str) -> list[str]:
    from assets.clip_bands import crop_for_clip

    # This clip's own measured text bands (#788); an unmeasured clip keeps the env default.
    top, bottom = crop_for_clip(clip)
    kept = max(0.2, 1.0 - top - bottom)
    # Even height and offset so libx264's yuv420p never sees an odd row count.
    band = (
        f"crop=iw:trunc(ih*{kept:.4f}/2)*2:0:trunc(ih*{top:.4f}/2)*2,"
        if (top + bottom) > 0
        else ""
    )
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
        f"{band}scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
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
    durations = {clip: d for clip in pool if (d := _probe(clip))}
    keys, windows = expand_pool(pool, durations)
    if len(keys) < _MIN_POOL:
        logger.info(
            "fast cut: only %d clip window(s) for '%s' - keeping the old background",
            len(keys),
            topic,
        )
        return None
    try:
        return _compose(keys, windows, topic, float(duration), words)
    except Exception as exc:
        logger.warning("fast cut failed; keeping the old background: %s", exc)
        return None


def _render_shot(clip: str, start: float, length: float, path: str) -> None:
    proc = subprocess.run(
        build_shot_command(os.path.abspath(clip), start, length, path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0 or not os.path.isfile(path):
        raise RuntimeError(f"shot from {clip}: {(proc.stderr or '')[-300:]}")


def _concat(list_path: str, output: str, duration: float) -> None:
    proc = subprocess.run(
        build_concat_command(list_path, output, duration),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0 or not os.path.isfile(output):
        raise RuntimeError(f"concat: {(proc.stderr or '')[-300:]}")


def shot_brightness(path: str, length: float) -> float | None:
    """Mean luma (0-255) of the shot, or None when it cannot be read.

    A 3-8 s shot (#792) can start in daylight and end in a tunnel, so anything past 4 s is
    read at a third and two thirds and scored on the darker of the two.
    """
    if length > 4.0:
        readings = [
            value
            for value in (_frame_luma(path, length / 3), _frame_luma(path, length * 2 / 3))
            if value is not None
        ]
        return min(readings) if readings else None
    return _frame_luma(path, length / 2)


def _frame_luma(path: str, at: float) -> float | None:
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-ss", f"{max(0.0, at):.3f}",
                "-i", path, "-frames:v", "1", "-vf", "scale=54:96,format=gray",
                "-f", "rawvideo", "-",
            ],
            capture_output=True,
            timeout=30,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    data = proc.stdout or b""
    if proc.returncode != 0 or not data:
        return None
    return sum(data) / len(data)


def _redraw(
    keys: list[str],
    windows: dict[str, tuple[str, float, float | None]],
    length: float,
    *,
    avoid: str,
    rng: random.Random,
) -> tuple[str, float]:
    """Another (clip, in-point) for a shot that came out too dark: a different file if any."""
    others = [k for k in keys if windows[k][0] != avoid] or list(keys)
    clip, offset, span = windows[rng.choice(others)]
    room = float(span) / 2 if span else 0.0
    return clip, round(offset + (rng.uniform(0.0, room) if room > 0.2 else 0.0), 3)


def prune_backgrounds(out_dir: str, *, days: int = _KEEP_TMP_DAYS) -> int:
    """Delete composed backgrounds older than `days`. Returns the megabytes reclaimed (#797)."""
    import time

    cutoff = time.time() - days * 86400
    freed = 0
    for name in os.listdir(out_dir) if os.path.isdir(out_dir) else []:
        path = os.path.join(out_dir, name)
        try:
            if not os.path.isfile(path) or os.path.getmtime(path) > cutoff:
                continue
            size = os.path.getsize(path)
            os.remove(path)
            freed += size
        except OSError as exc:
            logger.debug("background sweep skipped %s: %s", name, exc)
    megabytes = int(freed / (1024 * 1024))
    if megabytes:
        logger.info("fast cut: swept %d MB of old backgrounds", megabytes)
    return megabytes


def _compose(keys: list[str], windows, topic: str, duration: float, words):
    from assets.types import AssetResult
    from config.paths import DATA_DIR, ensure_data_dir

    shots = plan_windowed_shots(cut_points(duration, words), keys, windows)
    ensure_data_dir()
    out_dir = os.path.join(DATA_DIR, "tmp", "hybrid_backgrounds")
    os.makedirs(out_dir, exist_ok=True)
    prune_backgrounds(out_dir)
    output = os.path.join(out_dir, f"fastcut_{uuid.uuid4().hex[:12]}.mp4")
    work = tempfile.mkdtemp(prefix="fastcut_")
    try:
        rng = random.Random()

        def _one(i_shot):
            i, (clip, start, length) = i_shot
            path = os.path.join(work, f"shot_{i:04d}.mp4")
            for attempt in range(1 + _DARK_REDRAWS):
                _render_shot(clip, start, length, path)
                luma = shot_brightness(path, length)
                if luma is None or luma >= _MIN_LUMA or attempt == _DARK_REDRAWS:
                    break
                clip, start = _redraw(keys, windows, length, avoid=clip, rng=rng)
            return i, (clip, start, length), path

        # Shots are independent; the concat list is rebuilt in playback order afterwards.
        with ThreadPoolExecutor(max_workers=min(shot_workers(), len(shots))) as pool:
            done = list(pool.map(_one, enumerate(shots)))
        lines = []
        for i, shot, path in sorted(done, key=lambda row: row[0]):
            shots[i] = shot
            lines.append(f"file '{path.replace(os.sep, '/')}'")
        list_path = os.path.join(work, "shots.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        _concat(list_path, output, duration)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    try:
        from assets.clip_memory import record

        for clip in dict.fromkeys(c for c, _s, _l in shots):
            record(clip)
    except Exception as exc:
        logger.debug("clip memory record skipped: %s", exc)
    files = len({clip for clip, _s, _l in shots})
    logger.info("fast cut: %d shots from %d file(s) (%s)", len(shots), files, topic)
    return AssetResult(
        path=output,
        provider="fast_cut",
        query=topic,
        attribution=f"Gameplay (local), {len(shots)} shots",
    )


def _trim_audio(path: str, seconds: float) -> None:
    """Cut the copied voice track to `seconds` in place, so a preview costs a fraction."""
    trimmed = path + ".trim.mp3"
    proc = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-t", f"{float(seconds):.3f}", "-i", path,
         "-c", "copy", trimmed],
        capture_output=True,
        text=True,
        timeout=120,
    )  # fmt: skip
    if proc.returncode != 0 or not os.path.isfile(trimmed):
        raise RuntimeError(f"preview trim: {(proc.stderr or '')[-300:]}")
    os.replace(trimmed, path)


def render_preview(
    audio_path: str,
    topic: str,
    channel_id: str | None = None,
    *,
    out_dir: str | None = None,
    seconds: float | None = None,
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
    if seconds:
        _trim_audio(copy, float(seconds))
    sidecar = audio_path + ".words.json"
    script = ""
    if os.path.isfile(sidecar):
        with open(sidecar, encoding="utf-8") as f:
            words = [w for w in json.load(f) if isinstance(w, dict)]
        if seconds:
            words = [w for w in words if float(w.get("end") or 0.0) <= float(seconds)]
        with open(copy + ".words.json", "w", encoding="utf-8") as f:
            json.dump(words, f)
        script = " ".join(str(w.get("word") or "") for w in words)
    # A bare filename: render_vertical_video joins it under its own video folder and returns
    # the real path (a full path here nested it: video/output/tapin/preview/...).
    output, _background = render_vertical_video(
        copy, topic, f"{stem}.mp4", script.strip() or topic, channel_id
    )
    return str(output)
