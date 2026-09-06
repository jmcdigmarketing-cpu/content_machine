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
"""

from __future__ import annotations

from dataclasses import dataclass

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


def seed_and_brief_from_youtube(video_title: str, our_angle: str) -> tuple[str, str]:
    """Search the video's topic; keep OUR take as the brief, not a concatenated seed."""
    title = (video_title or "").strip()
    angle = (our_angle or "").strip()
    if angle:
        return title, angle
    return title, title
