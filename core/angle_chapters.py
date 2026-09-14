"""All angles in one long video (run 78).

The operator liked all five discovery angles and wanted them as chapters of one long
video, each chapter also good enough to stand alone as a Short. The script is still one
generation — every rewrite pass (recenter, reground, claim rewrite, trim, craft) runs on
it as usual — so chapter markers would not survive. Chapters are located *after* the
final script exists: an extract-tier call names each chapter's opening words, the answer
is verified against the text, and a deterministic keyword alignment takes over when it
cannot be trusted.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from core.chapters import _stamp
from core.logging import get_logger

logger = get_logger("core.angle_chapters")

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SENTENCE_END_RE = re.compile(r"[.!?]+[\"')\]]*\s+")
_DESCRIPTION_SPLIT_RE = re.compile(r"\s+[-–—]\s+")
_TRAILING_PAREN_RE = re.compile(r"\s*\([^()]{2,60}\)\s*$")
_TITLE_LIMIT = 100
_DISTANCE_WEIGHT = 2.0
_KEY_STOP = frozenset(
    """about after also been being between both could does each even from have into just
    like made make many more most much must only other over same should since some such
    than that their them then there these they this those through very what when where
    which while will with would your angle take""".split()
)


@dataclass
class AngleChapter:
    index: int
    title: str
    angle: str
    word_start: int
    char_start: int = 0


def angle_headline(angle: str, *, limit: int = _TITLE_LIMIT) -> str:
    """The title half of a generated angle: no "(Lens name)", no " - description"."""
    flat = " ".join((angle or "").split())
    head, *rest = _DESCRIPTION_SPLIT_RE.split(flat, maxsplit=1)
    text = head if rest and len(rest[0].split()) >= 6 else flat
    text = _TRAILING_PAREN_RE.sub("", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,:;")
    return text or flat[:limit]


def multi_angle_directive(angles: list[str]) -> str:
    """The brief block that turns one Extended script into one chapter per angle."""
    numbered = "\n".join(f"{i + 1}. {angle}" for i, angle in enumerate(angles))
    return (
        "ALL-ANGLES LONG VIDEO: this video covers EVERY angle below, in this order, as "
        "consecutive chapters.\n"
        "- Give each chapter a roughly equal share of the length.\n"
        "- Open every chapter with its own hook sentence that works with no context - each "
        "chapter will also be cut out and posted on its own as a Short.\n"
        '- Never refer back to an earlier chapter ("as I said", "earlier") and never announce '
        "chapter numbers; move to the next angle on a concrete fact, not a stock transition.\n"
        "- Land each chapter on its own payoff line before the next hook.\n"
        f"{numbered}"
    )


def token_start_times(word_timings: list[dict[str, Any]] | None) -> list[float]:
    """One start time per script token, so indices line up with ``_WORD_RE`` counts
    even when a TTS word is "real-world" (two tokens) or bare punctuation (none)."""
    out: list[float] = []
    for row in word_timings or []:
        if not isinstance(row, dict) or not isinstance(row.get("start"), int | float):
            continue
        tokens = len(_WORD_RE.findall(str(row.get("word") or "")))
        out.extend([float(row["start"])] * tokens)
    return out


def _sentence_starts(script: str) -> list[int]:
    starts = [0]
    for match in _SENTENCE_END_RE.finditer(script):
        if match.end() < len(script):
            starts.append(match.end())
    return starts


def _word_index_at(script: str, char: int) -> int:
    return len(_WORD_RE.findall(script[:char]))


def _keywords(text: str) -> set[str]:
    body = re.sub(r"\([^()]{2,60}\)", " ", text or "")
    out: set[str] = set()
    for token in _WORD_RE.findall(body.lower()):
        token = token.removesuffix("'s")
        if len(token) >= 4 and token not in _KEY_STOP and not token.isdigit():
            out.add(token)
    return out


def _llm_chapter_starts(script: str, angles: list[str]) -> list[int] | None:
    """Chapter start offsets from an extract-tier call, or None when it cannot be trusted."""
    numbered = "\n".join(f"{i + 1}. {angle_headline(a)}" for i, a in enumerate(angles))
    prompt = (
        "The script below covers these angles in order, one chapter each:\n"
        f"{numbered}\n\n"
        "For each angle, copy VERBATIM the first 6-10 words of the sentence where its "
        'chapter starts. Return JSON only: {"starts": ["...", "..."]} with exactly '
        f"{len(angles)} entries, in order.\n\nSCRIPT:\n{script}"
    )
    try:
        from core.llm_router import complete_json

        payload = complete_json(
            prompt, tier="extract", temperature=0.0, max_tokens=600, stage="angle_chapters"
        )
    except Exception as exc:
        logger.debug("chapter locator LLM skipped: %s", exc)
        return None
    rows = payload.get("starts") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) != len(angles):
        return None

    sentence_starts = _sentence_starts(script)
    out: list[int] = []
    for i, row in enumerate(rows):
        words = _WORD_RE.findall(str(row or ""))
        if not words:
            return None
        pattern = r"\W+".join(re.escape(word) for word in words)
        after = out[-1] + 1 if out else 0
        match = re.compile(pattern, re.I).search(script, after)
        if match is None:
            return None
        start = 0 if i == 0 else max(s for s in sentence_starts if s <= match.start())
        if out and start <= out[-1]:
            return None
        out.append(start)
    return out


def _keyword_chapter_starts(script: str, angles: list[str]) -> list[int]:
    """Deterministic fallback: the sentence that best names each angle, near where an
    even split would put it, always after the previous chapter."""
    starts = _sentence_starts(script)
    bounds = [*starts[1:], len(script)]
    sentences = [(s, script[s:e]) for s, e in zip(starts, bounds, strict=True)]
    word_at = [_word_index_at(script, s) for s, _text in sentences]
    total = max(1, len(_WORD_RE.findall(script)))
    n = len(angles)
    out = [0]
    for i in range(1, n):
        keys = _keywords(angles[i])
        target = total * i / n
        best: tuple[float, int] | None = None
        for j, (start, text) in enumerate(sentences):
            if start <= out[-1]:
                continue
            if len(sentences) - j < n - i:
                break
            overlap = len(keys & _keywords(text))
            score = overlap - _DISTANCE_WEIGHT * abs(word_at[j] - target) / total
            if best is None or score > best[0]:
                best = (score, start)
        if best is None:
            break
        out.append(best[1])
    return out


def locate_chapters(script: str, angles: list[str]) -> list[AngleChapter]:
    """One chapter per angle over the final script. Never raises; ``[]`` for no input."""
    angles = [a for a in (angles or []) if str(a).strip()]
    text = script or ""
    if not angles or not text.strip():
        return []
    starts = [0]
    if len(angles) > 1:
        starts = _llm_chapter_starts(text, angles) or _keyword_chapter_starts(text, angles)
    return [
        AngleChapter(
            index=i,
            title=angle_headline(angle),
            angle=angle,
            word_start=_word_index_at(text, char),
            char_start=char,
        )
        for i, (angle, char) in enumerate(zip(angles, starts, strict=False))
    ]


def chapter_lines(
    chapters: list[AngleChapter],
    *,
    word_timings: list[dict[str, Any]] | None = None,
    duration: float | None = None,
    total_words: int | None = None,
) -> str:
    """YouTube chapter lines titled by angle, timed from real word starts when known."""
    from core.script_length import WORDS_PER_SECOND

    times = token_start_times(word_timings)
    lines: list[str] = []
    for chapter in chapters:
        if chapter.word_start <= 0:
            seconds = 0.0
        elif chapter.word_start < len(times):
            seconds = times[chapter.word_start]
        elif duration and total_words:
            seconds = float(duration) * chapter.word_start / max(1, total_words)
        else:
            seconds = chapter.word_start / max(WORDS_PER_SECOND, 0.1)
        lines.append(f"{_stamp(seconds)} {chapter.title}")
    return "\n".join(lines)


def features_from_chapters(chapters: list[AngleChapter]) -> list[dict[str, Any]]:
    return [asdict(chapter) for chapter in chapters]


def chapters_from_features(rows: object) -> list[AngleChapter]:
    """Persisted ``angle_chapters`` back into chapters; unreadable rows are dropped."""
    out: list[AngleChapter] = []
    for i, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            continue
        try:
            out.append(
                AngleChapter(
                    index=int(row.get("index", i)),
                    title=str(row.get("title") or ""),
                    angle=str(row.get("angle") or row.get("title") or ""),
                    word_start=int(row.get("word_start") or 0),
                    char_start=int(row.get("char_start") or 0),
                )
            )
        except (TypeError, ValueError):
            continue
    return out
