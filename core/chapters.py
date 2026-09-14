"""YouTube chapter timestamps for Extended videos. Shorts skip."""

from __future__ import annotations

import json
import re
from typing import Any

from core.logging import get_logger

logger = get_logger("core.chapters")

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_CHAPTER_LINE_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s+\S")


def _label(sentence: str, *, limit: int = 40) -> str:
    words = re.sub(r"\s+", " ", (sentence or "").strip()).strip(" .")
    if not words:
        return "Chapter"
    if len(words) <= limit:
        return words
    return words[: limit - 1].rsplit(" ", 1)[0] or words[:limit]


def _stamp(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def chapter_block(
    script: str,
    duration: float | None = None,
    length_choice: str | None = None,
    word_timings: list[dict[str, Any]] | None = None,
) -> str:
    """Beat labels from the script. Empty for Shorts / missing input."""
    if str(length_choice or "").strip() != "4":
        return ""
    text = (script or "").strip()
    if not text:
        return ""
    parts = [p.strip() for p in _SENTENCE_RE.split(text) if p.strip()]
    if len(parts) < 2:
        parts = [text]
    span = float(duration or 0.0)
    if span <= 0:
        from core.script_length import WORDS_PER_SECOND

        span = max(60.0, len(text.split()) / WORDS_PER_SECOND)
    n = min(len(parts), 8)
    parts = parts[:n]
    timed_words = [
        row
        for row in (word_timings or [])
        if isinstance(row, dict)
        and str(row.get("word") or "").strip()
        and isinstance(row.get("start"), int | float)
    ]
    lines: list[str] = []
    word_index = 0
    for i, sentence in enumerate(parts):
        if i == 0:
            t = 0.0
        elif word_index < len(timed_words):
            t = float(timed_words[word_index]["start"])
        else:
            t = span * (i / n)
        lines.append(f"{_stamp(t)} {_label(sentence)}")
        word_index += len(_WORD_RE.findall(sentence))
    if len(lines) < 2:
        lines.append(f"{_stamp(span * 0.5)} Deep dive")
    if not lines[0].startswith("0:00"):
        lines[0] = "0:00 " + _label(parts[0])
    return "\n".join(lines)


def _replace_chapter_lines(description: str, old: str, new: str) -> str:
    if old and old in description:
        return description.replace(old, new, 1)
    lines = (description or "").splitlines()
    indexes = [i for i, line in enumerate(lines) if _CHAPTER_LINE_RE.match(line.strip())]
    if indexes and indexes == list(range(indexes[0], indexes[-1] + 1)):
        replacement = new.splitlines()
        return "\n".join(lines[: indexes[0]] + replacement + lines[indexes[-1] + 1 :])
    if new and "0:00" not in description:
        return f"{description.rstrip()}\n\n{new}".strip()
    return description


def refine_run_chapters(run_id: int | None, script: str, audio_path: str) -> str | None:
    """Replace estimated Extended chapters with real TTS word starts.

    Returns the persisted description, or ``None`` when the run is not Extended
    or no trustworthy timing sidecar exists.
    """
    if not run_id or not audio_path:
        return None
    try:
        from storage.repositories.content_runs import get_content_run_repository
        from video.subtitles import load_word_timings

        words = load_word_timings(audio_path)
        if not words:
            return None
        repo = get_content_run_repository()
        record = repo.get(int(run_id))
        if record is None:
            return None
        try:
            features = json.loads(record.features_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            features = {}
        angle_rows = features.get("angle_chapters")
        if angle_rows:
            # Run 78: an all-angles video's chapters are its angles, at real word starts.
            from core.angle_chapters import chapter_lines, chapters_from_features

            verified = chapter_lines(chapters_from_features(angle_rows), word_timings=words)
            description = _replace_chapter_lines(record.description or "", "", verified)
        else:
            if str(features.get("length_preset") or "") != "4":
                return None

            from core.script_length import WORDS_PER_SECOND, count_spoken_words

            estimated_duration = count_spoken_words(script) / max(WORDS_PER_SECOND, 0.1)
            old = chapter_block(script, duration=estimated_duration, length_choice="4")
            last_end = max(
                (
                    float(end)
                    for row in words
                    if isinstance(row, dict)
                    for end in [row.get("end")]
                    if isinstance(end, int | float)
                ),
                default=estimated_duration,
            )
            verified = chapter_block(
                script,
                duration=last_end,
                length_choice="4",
                word_timings=words,
            )
            description = _replace_chapter_lines(record.description or "", old, verified)
        features["chapters_timing_source"] = "word_timing"
        repo.update(
            int(run_id),
            {
                "description": description,
                "features_json": json.dumps(features),
            },
        )
        from core.run_trace import update_trace

        update_trace(int(run_id), {"chapters_timing_source": "word_timing"})
        return description
    except Exception as exc:
        logger.debug("verified chapter timing skipped for run %s: %s", run_id, exc)
        return None
