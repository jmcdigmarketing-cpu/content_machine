"""#406 per-persona style linter — warn only, never rewrite (MoneyWise ranges)."""

from __future__ import annotations

import json
import re

from core.logging import get_logger

logger = get_logger("core.persona_lint")

_FILLER_PHRASES = (
    "but here's the thing",
    "let's dive in",
    "without further ado",
    "at the end of the day",
    "buckle up",
    "game-changer",
    "in today's video",
    "delve",
)

# #891: the "it's not just X - it's Y" frame, as a pattern rather than a phrase list. The
# prompt banned one verbatim string and the model wrote every variant around it. Each
# pattern needs the intensifier ("just", "only", "about", "actually") that makes it the
# cliche, so a plain correction - "He isn't injured, he's suspended" - is not matched.
_NEG = r"(?:is|was|are|were|'s|'re)\s*n(?:o|')t"
_SAID = r"(?:it|this|that|they|he|she|we|you)\s*(?:'s|'re|is|are|was|were)"
_FRAME_IN_SENTENCE = (
    re.compile(rf"\b{_NEG}\s+(?:just|only|simply|merely)\b", re.I),
    re.compile(rf"\b{_NEG}\s+(?:about|really)\b.{{0,120}}?[,;:\u2014\u2013-]\s*{_SAID}\b", re.I),
    re.compile(r"\b(?:do|does|did)\s*n(?:o|')t\s+just\b", re.I),
    re.compile(r"\bnot\s+only\b.{0,120}?\bbut\b", re.I),
    re.compile(r"\bmore\s+than\s+just\b", re.I),
    re.compile(r"\bless\s+about\b.{0,80}?\bmore\s+about\b", re.I),
)
_FRAME_ANSWER = re.compile(rf"^\s*(?:but\s+|and\s+)?{_SAID}\s+(?:actually|really|about)\b", re.I)
_FRAME_NEGATED = re.compile(rf"\b{_NEG}\b", re.I)


def contrast_frames(text: str) -> list[str]:
    """Sentences (or sentence pairs) using the "not just X - it's Y" frame (#891)."""
    from core.script_length import split_spoken_sentences

    flat = (text or "").replace("\u2019", "'").replace("\u2018", "'")
    sentences = split_spoken_sentences(flat)
    hits: list[str] = []
    skip_next = False
    for i, sentence in enumerate(sentences):
        if skip_next:
            skip_next = False
            continue
        nxt = sentences[i + 1] if i + 1 < len(sentences) else ""
        if nxt and _FRAME_NEGATED.search(sentence) and _FRAME_ANSWER.search(nxt):
            hits.append(f"{sentence} {nxt}")
            skip_next = True
        elif any(p.search(sentence) for p in _FRAME_IN_SENTENCE):
            hits.append(sentence)
    return hits


# Spoken-number ranges that #327 already protects. Do not treat them as filler.
_RANGE_RE = re.compile(r"\b\d+\s*-\s*\d+\s*(%|years?|months?)\b", re.I)


def _channel_tells(channel_id: str) -> tuple[str, ...]:
    phrases = list(_FILLER_PHRASES)
    try:
        from pathlib import Path

        from config.paths import ROOT_DIR

        path = Path(ROOT_DIR) / "config" / "llm_tells.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        phrases.extend(str(p) for p in (data.get("shared") or []) if p)
        extra = data.get((channel_id or "").strip().lower()) or []
        phrases.extend(str(p) for p in extra if p)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    seen: set[str] = set()
    out: list[str] = []
    for phrase in phrases:
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            out.append(phrase)
    return tuple(out)


def lint_persona_script(script: str, *, channel_id: str = "tapin") -> list[str]:
    """Return banned-filler hits. Empty list on a clean script (no WARNING)."""
    text = script or ""
    if not text.strip():
        return []
    tells = _channel_tells(channel_id)
    # Pattern-catch: a MoneyWise range is not a style defect.
    hits = _has_filler(text, tells)
    hits += [f"contrast frame: {frame[:80]}" for frame in contrast_frames(text)]
    if channel_id == "moneywise" and _RANGE_RE.search(text) and not hits:
        return []
    if hits:
        logger.debug("persona lint %s: %s", channel_id, hits)
    return hits


def _has_filler(text: str, tells: tuple[str, ...] | None = None) -> list[str]:
    lowered = text.lower()
    phrases = tells if tells is not None else _FILLER_PHRASES
    return [p for p in phrases if p in lowered]
