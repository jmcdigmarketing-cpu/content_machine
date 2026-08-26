"""Grounded public-safe lower-third selection and timed ASS generation."""

from __future__ import annotations

import re

from core.fact_grounding import specific_entities

_TOKEN = re.compile(r"[A-Za-z0-9']+")
_UNSAFE = re.compile(r"https?://|www\.|@|\b(?:password|api[_ -]?key|secret|token)\b", re.I)


def select_grounded_labels(script: str, factual_text: str, *, max_labels: int = 3) -> list[str]:
    """Reuse fact-grounding entity rules; persist labels only, never source fact lines."""
    out: list[str] = []
    seen: set[str] = set()
    for entity in specific_entities(script or ""):
        label = " ".join(entity.split()).strip(" ,.:;!?")
        key = label.casefold()
        if (
            not label
            or len(label) > 48
            or _UNSAFE.search(label)
            or key in seen
            or not _exact_fact_phrase(factual_text, label)
        ):
            continue
        seen.add(key)
        out.append(label)
        if len(out) >= max(0, int(max_labels)):
            break
    return out


def _exact_fact_phrase(factual_text: str, label: str) -> bool:
    """Require one fact line to contain the complete public label in order."""
    wanted = _tokens(label)
    if not wanted:
        return False
    for fact in (factual_text or "").splitlines():
        available = _tokens(fact)
        for index in range(len(available) - len(wanted) + 1):
            if available[index : index + len(wanted)] == wanted:
                return True
    return False


def _ass_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02}:{secs:05.2f}"


def _ass_text(value: str) -> str:
    return value.replace("\\", r"\\").replace("{", r"\(").replace("}", r"\)").replace("\n", " ")


def _tokens(value: str) -> list[str]:
    return [token.casefold() for token in _TOKEN.findall(value)]


def _find_span(label: str, words: list[dict]) -> tuple[float, float] | None:
    wanted = _tokens(label)
    spoken = [_tokens(str(word.get("word") or "")) for word in words]
    flattened = [parts[0] if parts else "" for parts in spoken]
    if not wanted:
        return None
    for index in range(0, len(flattened) - len(wanted) + 1):
        if flattened[index : index + len(wanted)] != wanted:
            continue
        start = words[index].get("start")
        end = words[index + len(wanted) - 1].get("end")
        if start is None or end is None:
            return None
        return float(start), max(float(end) + 2.0, float(start) + 1.5)
    return None


def build_lower_thirds_ass(labels: list[str], words: list[dict] | None) -> str:
    """ASS overlays anchored to the first real spoken occurrence of each label."""
    if not labels or not words:
        return ""
    events: list[str] = []
    for label in labels:
        span = _find_span(label, words)
        if not span:
            continue
        start, end = span
        events.append(
            f"Dialogue: 1,{_ass_ts(start)},{_ass_ts(end)},LowerThird,,0,0,0,," f"{_ass_text(label)}"
        )
    if not events:
        return ""
    return (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        "Style: LowerThird,Arial,52,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,"
        "1,0,0,0,100,100,0,0,3,1,0,1,70,70,330,1\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        + "\n".join(events)
        + "\n"
    )
