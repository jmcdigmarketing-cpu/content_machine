"""Trim breath and dead air on generated audio (#404).

The word-count gate runs before any audio exists. This shortens the file later
duration checks read: leading and trailing silence go, and an internal gap
longer than 0.4s shrinks to 0.15s. Word timings move by the time removed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Any

from core.logging import get_logger

logger = get_logger("core.voice.dead_air")

_KEEP = 0.15
_MIN_GAP = 0.4
_START = re.compile(r"silence_start:\s*([0-9.]+)")
_END = re.compile(r"silence_end:\s*([0-9.]+)")


def cuts_for_silence(
    silences: list[tuple[float, float]],
    words: list[dict[str, Any]],
    *,
    keep: float = _KEEP,
    min_gap: float = _MIN_GAP,
) -> list[tuple[float, float]]:
    """``(time, seconds removed there)``. A short internal breath is not a cut."""
    starts = [float(word["start"]) for word in words if word.get("start") is not None]
    ends = [float(word["end"]) for word in words if word.get("end") is not None]
    if not starts or not ends:
        return []
    first = min(starts)
    last = max(ends)
    cuts: list[tuple[float, float]] = []
    for start, end in silences:
        length = float(end) - float(start)
        if length <= 0:
            continue
        if end <= first + 0.02 or start >= last - 0.02:
            cuts.append((float(start), length))
        elif length > min_gap:
            cuts.append((float(start) + keep, length - keep))
    return cuts


def shift_word_timings(
    words: list[dict[str, Any]], cuts: list[tuple[float, float]]
) -> tuple[list[dict[str, Any]], float]:
    """Word times after each cut, and the seconds removed."""

    def shift(moment: float) -> float:
        removed = sum(drop for at, drop in cuts if at < moment - 1e-9)
        return round(max(0.0, moment - removed), 3)

    shifted: list[dict[str, Any]] = []
    for word in words:
        item = dict(word)
        if item.get("start") is not None:
            item["start"] = shift(float(item["start"]))
        if item.get("end") is not None:
            item["end"] = shift(float(item["end"]))
        shifted.append(item)
    return shifted, round(sum(drop for _at, drop in cuts), 3)


def parse_silence_log(text: str) -> list[tuple[float, float]]:
    starts = [float(item) for item in _START.findall(text or "")]
    ends = [float(item) for item in _END.findall(text or "")]
    return [(start, ends[i]) for i, start in enumerate(starts) if i < len(ends)]


def kept_spans(duration: float, cuts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cursor = 0.0
    spans: list[tuple[float, float]] = []
    for start, drop in sorted(cuts):
        end = start + drop
        if start > cursor + 0.001:
            spans.append((cursor, start))
        cursor = max(cursor, end)
    if duration > cursor + 0.001:
        spans.append((cursor, duration))
    return [(start, end) for start, end in spans if end - start > 0.001]


def trim_dead_air(path: str) -> bool:
    """Trim ``path`` and its ``.words.json``. False leaves both unchanged.

    Missing ffmpeg is debug. A failed trim is a warning. Nothing to cut is quiet.
    """
    if not path or not os.path.isfile(path):
        return False
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        logger.debug("dead-air trim skipped: ffmpeg is not on PATH")
        return False
    try:
        silences = _detect(path)
        words = _load_words(path)
        cuts = cuts_for_silence(silences, words)
        if not cuts:
            return False
        duration = _duration(path, words, silences)
        spans = kept_spans(duration, cuts)
        if not spans:
            return False
        _rebuild(path, spans)
        shifted, _removed = shift_word_timings(words, cuts)
        _save_words(path, shifted)
        return True
    except Exception as exc:
        logger.warning("dead-air trim failed: %s", exc)
        return False


def _detect(path: str) -> list[tuple[float, float]]:
    proc = subprocess.run(
        ["ffmpeg", "-i", path, "-af", "silencedetect=n=-40dB:d=0.15", "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 and not proc.stderr:
        raise RuntimeError(f"silencedetect failed (rc={proc.returncode})")
    return parse_silence_log(proc.stderr or "")


def _duration(path: str, words: list[dict[str, Any]], silences: list[tuple[float, float]]) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        got = float((proc.stdout or "").strip())
        if got > 0:
            return got
    except ValueError:
        pass
    ends = [float(word["end"]) for word in words if word.get("end") is not None]
    ends.extend(end for _start, end in silences)
    return max(ends) if ends else 0.0


def _rebuild(path: str, spans: list[tuple[float, float]]) -> None:
    filters = []
    labels = []
    for i, (start, end) in enumerate(spans):
        filters.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[a{i}]")
    filters.append(f"{''.join(labels)}concat=n={len(spans)}:v=0:a=1[out]")
    dest = path + ".trim.mp3"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            path,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-c:a",
            "libmp3lame",
            "-qscale:a",
            "4",
            dest,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        if proc.returncode != 0 or not os.path.isfile(dest) or os.path.getsize(dest) <= 0:
            err = (proc.stderr or "")[-500:]
            raise RuntimeError(f"dead-air rebuild failed (rc={proc.returncode}): {err}")
        os.replace(dest, path)
    finally:
        if os.path.isfile(dest):
            try:
                os.remove(dest)
            except OSError:
                pass


def _load_words(path: str) -> list[dict[str, Any]]:
    sidecar = path + ".words.json"
    if not os.path.isfile(sidecar):
        return []
    try:
        with open(sidecar, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(loaded, list):
        return []
    return [word for word in loaded if isinstance(word, dict)]


def _save_words(path: str, words: list[dict[str, Any]]) -> None:
    sidecar = path + ".words.json"
    if not os.path.isfile(sidecar):
        return
    with open(sidecar, "w", encoding="utf-8") as handle:
        json.dump(words, handle)
