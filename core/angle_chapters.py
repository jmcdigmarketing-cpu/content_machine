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
from dataclasses import asdict, dataclass, replace
from typing import Any

from apis.topic_tokens import FUNCTION_WORDS
from core.chapters import youtube_chapter_lines
from core.logging import get_logger

logger = get_logger("core.angle_chapters")

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SENTENCE_END_RE = re.compile(r"[.!?]+[\"')\]]*\s+")
_DESCRIPTION_SPLIT_RE = re.compile(r"\s+[-–—]\s+")
_TRAILING_PAREN_RE = re.compile(r"\s*\([^()]{2,60}\)\s*$")
_TITLE_LIMIT = 100
_DISTANCE_WEIGHT = 2.0
_WINDOW_SHARE = 0.5  # #773: a chapter pick stays within half a share of its even-split target
_KEY_STOP = FUNCTION_WORDS | frozenset(
    [
        "about",
        "after",
        "also",
        "been",
        "being",
        "between",
        "both",
        "could",
        "does",
        "each",
        "even",
        "from",
        "have",
        "into",
        "just",
        "like",
        "made",
        "make",
        "many",
        "more",
        "most",
        "much",
        "must",
        "only",
        "other",
        "over",
        "same",
        "should",
        "since",
        "some",
        "such",
        "than",
        "that",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "very",
        "what",
        "when",
        "where",
        "which",
        "while",
        "will",
        "with",
        "would",
        "your",
        "angle",
        "take",
    ]
)


@dataclass
class AngleChapter:
    index: int
    title: str
    angle: str
    word_start: int
    char_start: int = 0
    placed_by: str = ""  # #755 - "llm" | "keyword" | "single"; "" on rows from before it
    # #1009 - where the title came from ("chapter" | "angle" | "sentence"; "" before it) and
    # why the angle's own headline was refused, if it was.
    title_source: str = ""
    title_note: str = ""


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


def _llm_chapter_starts(
    script: str, angles: list[str], titles: list[str] | None = None
) -> list[int | None] | None:
    """Chapter start offsets from an extract-tier call, or None when it cannot be trusted.

    #1010: an entry is None when the model says the script never covers that angle - run
    120's chapter 5 was never written, and the keyword fallback placed it on a late sentence
    anyway, so the description and the Shorts list offered a 0:06 "chapter".
    """
    numbered = "\n".join(f"{i + 1}. {angle_headline(a)}" for i, a in enumerate(angles))
    prompt = (
        "The script below covers these angles in order, one chapter each:\n"
        f"{numbered}\n\n"
        "For each angle, copy VERBATIM the first 6-10 words of the sentence where its "
        'chapter starts, or "" when the script never gets to that angle. Also give each '
        "chapter a title of at most 8 words, using only names, numbers and claims that "
        "chapter itself says (#1009). Return JSON only: "
        f'{{"starts": ["...", "..."], "titles": ["...", "..."]}} with exactly {len(angles)} '
        f"entries each, in order.\n\nSCRIPT:\n{script}"
    )
    try:
        from core.llm_router import complete_json

        payload = complete_json(
            prompt, tier="extract", temperature=0.0, max_tokens=600, stage="angle_chapters"
        )
    except Exception as exc:
        logger.warning("chapter locator: LLM call failed (%s) - keyword fallback", exc)
        return None
    rows = payload.get("starts") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) != len(angles):
        # #755: the first live run fell back with no trace of why.
        logger.warning(
            "chapter locator: wanted %d starts, got %r - keyword fallback",
            len(angles),
            rows if isinstance(rows, list) else type(payload).__name__,
        )
        return None

    named = payload.get("titles") if isinstance(payload, dict) else None
    if titles is not None and isinstance(named, list) and len(named) == len(angles):
        titles[:] = [" ".join(str(t or "").split()) for t in named]
    sentence_starts = _sentence_starts(script)
    out: list[int | None] = []
    placed: list[int] = []
    for i, row in enumerate(rows):
        words = _WORD_RE.findall(str(row or ""))
        if not words:
            if i == 0:
                logger.warning("chapter locator: start 1 is empty - keyword fallback")
                return None
            logger.info("chapter locator: angle %d is not in the script", i + 1)
            out.append(None)
            continue
        pattern = r"\W+".join(re.escape(word) for word in words)
        after = placed[-1] + 1 if placed else 0
        match = re.compile(pattern, re.I).search(script, after)
        if match is None:
            logger.warning(
                "chapter locator: start %d %r not found in order - keyword fallback",
                i + 1,
                str(row)[:80],
            )
            return None
        start = 0 if i == 0 else max(s for s in sentence_starts if s <= match.start())
        if placed and start <= placed[-1]:
            logger.warning(
                "chapter locator: start %d %r shares a sentence with the one before - "
                "keyword fallback",
                i + 1,
                str(row)[:80],
            )
            return None
        out.append(start)
        placed.append(start)
    return out


def _keyword_chapter_starts(script: str, angles: list[str]) -> list[int]:
    """Deterministic fallback: the sentence that best names each angle, near where an
    even split would put it, always after the previous chapter.

    #773: keyword overlap used to outrank the distance penalty outright, so live run 78 put
    chapters at 0/208/775/835/946 of 1,007 words - one chapter of 567, two of ~60. Each pick
    is now confined to a window around its even-split target, widened only when the window
    holds no sentence at all.
    """
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
        share = total / n
        best: tuple[float, int] | None = None
        # Half a chapter's share either side of the target first; only if nothing sits in
        # that window does it widen, so an angle named once at the end cannot drag its
        # chapter there and starve the ones between.
        for window in (share * _WINDOW_SHARE, share, float(total)):
            for j, (start, text) in enumerate(sentences):
                if start <= out[-1]:
                    continue
                if len(sentences) - j < n - i:
                    break
                if abs(word_at[j] - target) > window:
                    continue
                overlap = len(keys & _keywords(text))
                score = overlap - _DISTANCE_WEIGHT * abs(word_at[j] - target) / total
                if best is None or score > best[0]:
                    best = (score, start)
            if best is not None:
                break
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
    starts: list[int | None] = [0]
    placed_by = "single"
    model_titles: list[str] = []
    if len(angles) > 1:
        llm_starts = _llm_chapter_starts(text, angles, model_titles)
        if llm_starts:
            starts, placed_by = llm_starts, "llm"
        else:
            starts, placed_by = list(_keyword_chapter_starts(text, angles)), "keyword"
            model_titles = []
    named = model_titles if len(model_titles) == len(angles) else [""] * len(angles)
    placed = [
        (angle, char, title)
        for angle, char, title in zip(angles, starts, named, strict=False)
        if char is not None  # #1010: an angle the script never reaches gets no chapter
    ]
    bounds = [*[char for _a, char, _t in placed[1:]], len(text)]
    chapters: list[AngleChapter] = []
    for i, ((angle, char, model_title), end) in enumerate(zip(placed, bounds, strict=True)):
        title, source, note = choose_chapter_title(
            text[char:end], model_title=model_title, angle=angle, script=text
        )
        chapters.append(
            AngleChapter(
                index=i,
                title=title,
                angle=angle,
                word_start=_word_index_at(text, char),
                char_start=char,
                placed_by=placed_by,
                title_source=source,
                title_note=note,
            )
        )
    return chapters


_TITLE_NUMBER_RE = re.compile(r"\d[\d,.]*")
_TITLE_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\u2019]*|[^\sA-Za-z]+")


def _title_names(title: str) -> list[list[str]]:
    """Runs of two or more capitalised words in a title that are not function words - the
    names. Title Case alone ("Will It Crash or Deliver?") yields single words, not runs."""
    runs: list[list[str]] = []
    run: list[str] = []
    for token in _TITLE_TOKEN_RE.findall(title or ""):
        word = re.sub(r"['\u2019]s$", "", token)
        if word[:1].isupper() and word.lower() not in FUNCTION_WORDS:
            run.append(word)
            continue
        if len(run) >= 2:
            runs.append(run)
        run = []
    if len(run) >= 2:
        runs.append(run)
    return runs


def chapter_title_problem(title: str, section: str, *, script: str = "", today: Any = None) -> str:
    """Why ``title`` cannot label ``section``, or "" when the script supports it (#1009).

    A number or a multi-word name the script never says (run 119: "UFC 305 adds Kamaru
    Usman"), a year that has passed used as a prediction, or a numbered event that has
    happened. Names and numbers are checked against the whole ``script`` when given - a
    chapter need not repeat the video's subject ("GTA 6") - and dates against the section.
    Deterministic and network-free.
    """
    from core.facts.date_math import find_elapsed_mismatches
    from core.facts.event_dates import stale_angle_reason

    text = script or section or ""
    lower = text.lower()
    for raw in _TITLE_NUMBER_RE.findall(title or ""):
        number = raw.strip(",.")
        if number and not re.search(rf"(?<![\d.]){re.escape(number)}(?!\d)", text):
            return f"'{number}' is not in the chapter"
    for run in _title_names(title):
        if any(len(word) >= 4 and word.lower()[:4] not in lower for word in run):
            return f"'{' '.join(run)}' is not in the chapter"
    stale = stale_angle_reason(title, today=today, facts=section or "")
    if stale:
        return stale
    elapsed = find_elapsed_mismatches(title, section or "", today=today)
    return elapsed[0] if elapsed else ""


def choose_chapter_title(
    section: str,
    *,
    model_title: str = "",
    angle: str = "",
    script: str = "",
    today: Any = None,
) -> tuple[str, str, str]:
    """(title, source, note) for one chapter (#1009).

    The title written from the chapter comes first, then the angle's headline, then a label
    from the chapter's first sentence. ``note`` says why the angle headline was refused -
    the run card's "retitled" line - and is "" when it would have passed.
    """
    from core.chapters import _label

    headline = angle_headline(angle) if angle else ""
    note = chapter_title_problem(headline, section, script=script, today=today) if headline else ""
    candidate = " ".join((model_title or "").split())[:_TITLE_LIMIT]
    if candidate and not chapter_title_problem(candidate, section, script=script, today=today):
        return candidate, "chapter", note
    if headline and not note:
        return headline, "angle", ""
    first = (_SENTENCE_END_RE.split((section or "").strip(), maxsplit=1) or [""])[0]
    return _label(first), "sentence", note


# #1010: about 8 s at the spoken pace, under YouTube's 10 s chapter floor. A shorter
# "chapter" is a sentence the locator had to put somewhere - run 120's chapter 4 was offered
# as a 0:06 Short (about 15 words).
MIN_CHAPTER_WORDS = 20


def uncovered_angles(script: str, angles: list[str]) -> list[int]:
    """Indices of the chosen angles the script never gets to, in order (#1010).

    Deterministic and lenient: an angle counts as covered when any sentence at or after the
    previous angle's first mention shares one of its keywords. The opening angle is the
    video's start, so it is never missing. Run 120 stopped inside chapter 4 and never named
    "legal gray zone" - that is what this catches; a paraphrased angle is not flagged.
    """
    text = script or ""
    starts = _sentence_starts(text)
    bounds = [*starts[1:], len(text)]
    sentences = [_keywords(text[s:e]) for s, e in zip(starts, bounds, strict=True)]
    missing: list[int] = []
    pos = 0
    for i, angle in enumerate(angles or []):
        keys = _keywords(angle)
        if i == 0 or not keys:
            continue
        hit = next((j for j in range(pos, len(sentences)) if keys & sentences[j]), None)
        if hit is None:
            missing.append(i)
            continue
        pos = hit
    return missing


def drop_thin_chapters(
    script: str, chapters: list[AngleChapter], *, min_words: int = MIN_CHAPTER_WORDS
) -> tuple[list[AngleChapter], list[AngleChapter]]:
    """Fold a chapter too short to stand alone back into the one before it (#1010).

    Returns (kept, dropped). Chapter 1 opens the video and is never dropped; the kept
    chapters are renumbered so the description, the report and the Shorts list agree.
    """
    text = script or ""
    if len(chapters) < 2:
        return list(chapters), []
    bounds = [*[c.char_start for c in chapters[1:]], len(text)]
    kept: list[AngleChapter] = []
    dropped: list[AngleChapter] = []
    for i, (chapter, end) in enumerate(zip(chapters, bounds, strict=True)):
        words = len(_WORD_RE.findall(text[chapter.char_start : end]))
        if i > 0 and words < min_words:
            dropped.append(chapter)
        else:
            kept.append(chapter)
    return [replace(c, index=i) for i, c in enumerate(kept)], dropped


# A chapter Short is watched with no lead-in, so its first word cannot point backwards.
# Live run 79: cuts 2, 4 and 5 opened "So the real question...", "But let's get concrete...",
# "And it's not just about microtransactions anymore." (#770)
_OPENER_CONNECTIVES = ("so", "but", "and", "now", "yet", "still", "because", "plus", "anyway")
_SENTENCE_BREAK_RE = re.compile(r"[.!?]")


def _trimmed_opener(sentence: str) -> str:
    """The sentence without its leading connective, or "" when it cannot lose one cleanly."""
    match = re.match(r"\s*([A-Za-z']+)([,\s]+)(.*)", sentence, re.S)
    if not match:
        return ""
    first, _gap, rest = match.groups()
    if first.lower() not in _OPENER_CONNECTIVES or not rest.strip():
        return ""
    rest = rest.lstrip()
    # "And then everything changed." -> "then everything changed." is not a sentence an
    # operator would publish, so leave it and say so instead.
    if rest.split()[0].lower() in ("then", "so", "now", "yet", "also", "too"):
        return ""
    return rest[:1].upper() + rest[1:]


def trim_chapter_openers(
    script: str, chapters: list[AngleChapter]
) -> tuple[str, list[AngleChapter], list[str]]:
    """Drop a back-referencing first word from each chapter's opening sentence (#770).

    Returns the edited script, chapters shifted by the words removed before them, and one note
    per chapter touched or still opening on a connective. Chapter 1 is left alone - it opens
    the video, where a connective reads as a voice, not a dangling reference.
    """
    text = script or ""
    if not text.strip() or len(chapters) < 2:
        return text, chapters, []

    edits: list[tuple[int, int, str]] = []  # (original char_start, chars removed, sentence)
    notes: list[str] = []
    shift = 0  # chars already removed by earlier edits, so later offsets still land
    for chapter in chapters[1:]:
        start = max(0, int(chapter.char_start) - shift)
        if start >= len(text):
            continue
        end = _SENTENCE_BREAK_RE.search(text, start)
        sentence = text[start : (end.end() if end else len(text))]
        trimmed = _trimmed_opener(sentence)
        first_word = (sentence.strip().split() or [""])[0].strip(",").lower()
        if not trimmed:
            if first_word in _OPENER_CONNECTIVES:
                notes.append(
                    f"chapter {chapter.index + 1} still opens on '{first_word}': "
                    f"{' '.join(sentence.split()[:8])}"
                )
            continue
        removed = len(sentence) - len(trimmed)
        notes.append(
            f"chapter {chapter.index + 1} opener: dropped '{first_word}' -> "
            f"{' '.join(trimmed.split()[:8])}"
        )
        edits.append((int(chapter.char_start), removed, sentence))
        text = text[:start] + trimmed + text[start + len(sentence) :]
        shift += removed

    if not edits:
        return text, chapters, notes

    shifted: list[AngleChapter] = []
    for chapter in chapters:
        removed_chars = sum(chars for start, chars, _s in edits if start < chapter.char_start)
        char_start = max(0, int(chapter.char_start) - removed_chars)
        shifted.append(
            replace(chapter, word_start=_word_index_at(text, char_start), char_start=char_start)
        )
    return text, shifted, notes


def chapter_lines(
    chapters: list[AngleChapter],
    *,
    word_timings: list[dict[str, Any]] | None = None,
    duration: float | None = None,
    total_words: int | None = None,
    channel_id: str | None = None,
) -> str:
    """YouTube chapter lines titled by angle, timed from real word starts when known."""
    from core.script_length import spoken_words_per_second

    times = token_start_times(word_timings)
    points: list[tuple[float, str]] = []
    for chapter in chapters:
        if chapter.word_start <= 0:
            seconds = 0.0
        elif chapter.word_start < len(times):
            seconds = times[chapter.word_start]
        elif duration and total_words:
            seconds = float(duration) * chapter.word_start / max(1, total_words)
        else:
            seconds = chapter.word_start / max(spoken_words_per_second(channel_id), 0.1)
        points.append((seconds, chapter.title))
    return youtube_chapter_lines(points)


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
                    placed_by=str(row.get("placed_by") or ""),
                    title_source=str(row.get("title_source") or ""),
                    title_note=str(row.get("title_note") or ""),
                )
            )
        except (TypeError, ValueError):
            continue
    return out


def chapter_card_lines(features: dict[str, Any] | None) -> list[str]:
    """Run-card lines: chapters retitled (#1009), written or left out (#1010)."""
    feats = features or {}
    written = feats.get("chapters_written") or {}
    lines: list[str] = []
    for chapter in chapters_from_features(feats.get("angle_chapters")):
        if chapter.title_note and chapter.title_source != "angle":
            lines.append(
                f"Chapter {chapter.index + 1} retitled - the angle's headline was refused: "
                f"{chapter.title_note}"
            )
    if written.get("written") and written.get("missing"):
        nums = ", ".join(str(n) for n in written["missing"])
        lines.append(f"Chapter {nums} was not in the first draft - written from the facts")
    for headline in feats.get("chapters_missing") or []:
        lines.append(f"Chapter not written, left out of the chapter list: {headline}")
    return lines
