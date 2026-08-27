"""YouTube chapter timestamps for Extended videos. Shorts skip."""

from __future__ import annotations

import re

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


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
    lines: list[str] = []
    for i, sentence in enumerate(parts):
        t = 0.0 if i == 0 else span * (i / n)
        lines.append(f"{_stamp(t)} {_label(sentence)}")
    if len(lines) < 2:
        lines.append(f"{_stamp(span * 0.5)} Deep dive")
    if not lines[0].startswith("0:00"):
        lines[0] = "0:00 " + _label(parts[0])
    return "\n".join(lines)
