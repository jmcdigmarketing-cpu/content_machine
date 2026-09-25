"""
Parse a pasted video idea (option 5) into a clean seed + creative angle.

Idea generators (and the user's own notes) often paste structured blocks with
scaffolding the pipeline shouldn't ingest, e.g.:

    Idea illustration
    Marvel Rivals Rank Analysis: Why The Competitive Grind ...
    We bypass the hollow dopamine loops of modern shooters to dissect ...

    Develop idea
    Save idea
    Why this could fit your channel
    1
    Interdisciplinary Tactical Synthesis
    ...

This module extracts the **title** (the searchable seed) and the **thesis**
(the creative angle that should shape the script), dropping UI labels and the
"why this fits" rationale. Plain single-line topics and bare URLs pass through
unchanged.

Typed *thoughts* (run 77: a four-question GTA 6 thesis at the Topic prompt) are
not a search string. ``search_seed_from_thoughts`` pulls the short subject out
for discovery; the thoughts themselves stay the brief.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.logging import get_logger

logger = get_logger("core.idea_intake")

# Exact (lowercased) UI labels emitted by idea generators — never content.
_SCAFFOLD_LABELS = {
    "idea illustration",
    "idea",
    "video idea",
    "develop idea",
    "save idea",
    "edit idea",
    "regenerate",
    "description",
    "thesis",
    "title",
}

# Once a line starts the rationale section, everything after it is meta.
_RATIONALE_MARKERS = (
    "why this could fit",
    "why this fits",
    "why this works",
    "why it fits",
    "why this could work",
)

_SENTENCE_BREAK = re.compile(r"[?!.;]+(?=\s|$)|\s+[-–—]\s+|\n")
# Conversational lead-ins that are about the operator, not the subject.
_LEAD_FILLER = re.compile(
    r"^(?:(?:my\s+)?thoughts?|idea|i\s+think|i\s+feel\s+like|honestly|basically|"
    r"so|ok(?:ay)?|imo)\b[\s:,.-]*",
    re.I,
)
_TRAILING_FILLER = re.compile(r"[\s:,.-]+(?:my\s+)?(?:thoughts?|ideas?|notes?)[\s:.]*$", re.I)
# A sequel / season token that belongs to the franchise name ("GTA 6", "season 4").
_VERSION_AFTER = r"\s+((?:season|chapter|part|patch|update)\s+\d+(?:\.\d+)?|\d{1,4}|[IVX]{1,4})\b"
_SEED_MAX_WORDS = 8
_THOUGHT_MIN_WORDS = 12


@dataclass
class ParsedIdea:
    title: str
    thesis: str
    seed_topic: str  # concise — drives discovery / signal search
    angle: str  # full creative brief — shapes the script
    is_rich: bool  # True when a structured/multi-part idea was detected


def _is_scaffold(line: str) -> bool:
    low = line.lower().strip().strip(":").strip()
    return low in _SCAFFOLD_LABELS


def _starts_rationale(line: str) -> bool:
    low = line.lower().strip()
    return any(low.startswith(m) for m in _RATIONALE_MARKERS)


def _seed_from_title(title: str) -> str:
    """A title like 'X: long philosophical clause' searches better as just 'X'."""
    if ":" in title:
        head = title.split(":", 1)[0].strip()
        if len(head.split()) >= 3:
            return head
    return title


def looks_like_thoughts(text: str) -> bool:
    """Several sentences or a long run-on — an idea in prose, not a search string."""
    flat = " ".join((text or "").split())
    if not flat:
        return False
    clauses = [part for part in _SENTENCE_BREAK.split(flat) if part and part.strip()]
    return len(flat.split()) > _THOUGHT_MIN_WORDS or len(clauses) >= 2


def _first_clause(text: str) -> str:
    head = _SENTENCE_BREAK.split(text, maxsplit=1)[0]
    return " ".join(head.replace("/", " ").split()).strip(" ,:")


def _cap_words(text: str) -> str:
    return " ".join(text.split()[:_SEED_MAX_WORDS]).strip(" ,:;")


def search_seed_from_thoughts(text: str) -> str:
    """The subject to search for, out of an idea typed as prose. Never raises.

    Named subjects first (franchise anchors with their sequel/season token, then
    people and proper nouns, in the order typed); a bare franchise name or no name at
    all falls back to the first short clause. Anything that does not read as thoughts
    is returned unchanged, so a plain topic searches exactly as before.
    """
    flat = " ".join((text or "").split())
    if not looks_like_thoughts(flat):
        return flat
    body = _LEAD_FILLER.sub("", flat).strip() or flat

    found: list[tuple[int, int, str, bool]] = []  # start, end, term, has_version

    def _overlaps(start: int, end: int) -> bool:
        return any(start < e and s < end for s, e, _t, _v in found)

    try:
        from core.channel_context import extract_anchors

        for anchor in extract_anchors(body):
            match = re.search(rf"\b{re.escape(anchor)}\b(?:{_VERSION_AFTER})?", body, re.I)
            if match and not _overlaps(*match.span()):
                version = match.group(1)
                term = f"{anchor} {version}" if version else anchor
                found.append((match.start(), match.end(), term, bool(version)))
    except Exception as exc:
        logger.debug("seed anchor extraction skipped: %s", exc)
    try:
        from core.fact_grounding import specific_entities

        for entity in specific_entities(body):
            idx = body.find(entity)
            if idx >= 0 and not _overlaps(idx, idx + len(entity)):
                found.append((idx, idx + len(entity), entity, True))
    except Exception as exc:
        logger.debug("seed entity extraction skipped: %s", exc)

    found.sort()
    terms: list[str] = []
    for _start, _end, term, _version in found:
        if term.lower() not in {t.lower() for t in terms}:
            terms.append(term)

    clause = _first_clause(body)
    bare_anchor = len(found) == 1 and not found[0][3]
    if terms and not bare_anchor:
        return _cap_words(" ".join(terms))
    if clause and len(clause.split()) <= 6 and (not terms or terms[0].lower() in clause.lower()):
        return clause
    if terms:
        return terms[0]
    return _cap_words(clause or body)


_OPINION_CUE = re.compile(
    r"\b(i think|i thought|i feel|i believe|i bet|i say|i'd argue|i reckon|imo|"
    r"in my opinion|my take|my bet|my money)\b",
    re.I,
)


def operator_quotes(brief: str, *, limit: int = 2) -> list[str]:
    """First-person opinion sentences from the operator's own words (#543).

    Typed thoughts are the brief since run 77, but the writer paraphrased them. These are
    the lines the script must carry verbatim.
    """
    flat = " ".join((brief or "").split())
    out: list[str] = []
    for part in _SENTENCE_BREAK.split(flat):
        text = (part or "").strip(" ,;:-")
        if not text or len(text.split()) < 4 or not _OPINION_CUE.search(text):
            continue
        if text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def quote_survived(script: str, quotes: list[str]) -> bool:
    """True when the script still carries one of the operator's lines, not a paraphrase."""

    def _flat(text: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9' ]+", " ", (text or "").lower()).split())

    haystack = _flat(script)
    for quote in quotes or []:
        words = _flat(_OPINION_CUE.sub(" ", quote or "")).split()
        if len(words) < 4:
            continue
        if " ".join(words[:8]) in haystack:
            return True
        if len(words) > 8 and " ".join(words[-8:]) in haystack:
            return True
    return False


def parse_pasted_idea(text: str) -> ParsedIdea:
    """Extract (title, thesis, seed_topic, angle) from raw pasted idea text."""
    raw = text or ""
    lines = [ln.strip() for ln in raw.splitlines()]

    content: list[str] = []
    for ln in lines:
        if not ln:
            continue
        if _starts_rationale(ln):
            break  # rationale + everything after it is meta
        if _is_scaffold(ln):
            continue
        # Bare list ordinals from rationale blocks ("1", "2.") — skip
        if ln.rstrip(".").isdigit():
            continue
        content.append(ln)

    if not content:
        flat = " ".join(raw.split())
        return ParsedIdea(
            title=flat[:120], thesis="", seed_topic=flat[:120], angle=flat, is_rich=False
        )

    title = content[0]
    thesis = " ".join(content[1:]).strip()
    is_rich = bool(thesis) or len([ln for ln in lines if ln]) > 1

    seed_topic = _seed_from_title(title)
    if seed_topic == title and looks_like_thoughts(title):
        # Run 77: the whole four-question thesis went to every search signal.
        seed_topic = search_seed_from_thoughts(title)
    elif is_rich:
        # "GTA 6 thoughts" over a pasted paragraph: the label word is not the subject.
        seed_topic = (
            _TRAILING_FILLER.sub("", _LEAD_FILLER.sub("", seed_topic)).strip() or seed_topic
        )
    angle = f"{title} — {thesis}".strip(" —") if thesis else title

    return ParsedIdea(
        title=title,
        thesis=thesis,
        seed_topic=seed_topic,
        angle=angle,
        is_rich=is_rich,
    )


def creative_brief_for_run(parsed: ParsedIdea) -> str:
    """What the writer should see. A one-line idea is still the assignment."""
    return (parsed.angle or parsed.seed_topic or parsed.title or "").strip()


def brief_for_typed_topic(topic: str) -> str:
    """Option 1 type-your-own: the typed thesis is the editorial angle.

    Run 76 typed four questions at the best-bet prompt; `creative_brief` stayed
    empty, so the script prompt never got an EDITORIAL ANGLE block.
    """
    return creative_brief_for_run(parse_pasted_idea(topic or ""))


def seed_and_brief_from_youtube(video_title: str, our_angle: str) -> tuple[str, str]:
    """Search the video's topic; keep OUR take as the brief, not a concatenated seed."""
    title = (video_title or "").strip()
    angle = (our_angle or "").strip()
    if angle:
        return title, angle
    return title, title
