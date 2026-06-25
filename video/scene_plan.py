"""Scene plan: split a script into timed beats, each with its own B-roll query.

The render loops ONE background clip for the whole video. Scene-matching instead
cuts between several clips, each chosen for the beat it covers — far more engaging
and a retention lever (the visual changes as the topic does). This module produces
the *plan* (which query, which time window per beat); fetching + concatenation live
in `assets/composite`, gated behind `SCENE_MATCHED_BROLL` with a full fallback to
the current single/hybrid background.

Pure + deterministic (no LLM, no I/O) so it's unit-tested. Uses real word timings
when available for accurate beat boundaries, else proportional spacing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Words that never make a good B-roll search term.
_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "of",
    "for",
    "to",
    "in",
    "on",
    "at",
    "as",
    "by",
    "with",
    "from",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "will",
    "would",
    "can",
    "could",
    "should",
    "his",
    "her",
    "their",
    "your",
    "you",
    "they",
    "we",
    "he",
    "she",
    "what",
    "why",
    "how",
    "when",
    "who",
    "now",
    "then",
    "here",
    "there",
    "just",
    "really",
    "very",
    "more",
    "most",
    "than",
    "into",
    "about",
    "after",
    "before",
    "over",
    "out",
    "up",
    "down",
}


@dataclass
class Scene:
    query: str
    start: float
    end: float
    text: str


def _beat_keyword(text: str) -> str:
    """Most salient term in a beat: a multi-word proper noun, else the longest word."""
    proper = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", text)
    if proper:
        return proper[0]
    caps = [w for w in re.findall(r"[A-Z][a-zA-Z]{2,}", text) if not w.isupper()]
    if caps:
        return caps[0]
    words = [w for w in re.findall(r"[a-zA-Z]{4,}", text.lower()) if w not in _STOP]
    return max(words, key=len) if words else ""


def plan_scenes(
    script: str,
    topic: str,
    duration: float,
    *,
    words: list[dict] | None = None,
    max_scenes: int = 4,
) -> list[Scene]:
    """Split into ≤`max_scenes` timed beats, each with a topic+beat B-roll query."""
    tokens = [t for t in (script or "").split() if t]
    if not tokens or duration <= 0:
        return []
    n = max(1, min(max_scenes, len(tokens) // 8 or 1))
    if n == 1:
        kw = _beat_keyword(script)
        q = f"{topic} {kw}".strip() if kw else topic
        return [Scene(query=q, start=0.0, end=float(duration), text=script.strip())]

    # Even word-count slices.
    bounds = [round(i * len(tokens) / n) for i in range(n + 1)]
    use_words = bool(words) and len(words) >= len(tokens) * 0.6
    scenes: list[Scene] = []
    for i in range(n):
        lo, hi = bounds[i], bounds[i + 1]
        if hi <= lo:
            continue
        text = " ".join(tokens[lo:hi])
        if use_words:
            start = float(words[min(lo, len(words) - 1)].get("start") or 0.0)
            end = float(words[min(hi, len(words)) - 1].get("end") or start)
        else:
            start = duration * lo / len(tokens)
            end = duration * hi / len(tokens)
        if i == n - 1:
            end = float(duration)
        kw = _beat_keyword(text)
        query = f"{topic} {kw}".strip() if kw else topic
        scenes.append(Scene(query=query, start=round(start, 3), end=round(end, 3), text=text))
    return scenes
