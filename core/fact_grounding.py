"""
Post-generation fact-grounding check.

The script prompt forbids naming specifics — heroes, fighters, products, patch
versions — that aren't in VERIFIED FACTS, but the model still occasionally
invents them (e.g. "Emma Frost" / "Radiant Shore" appeared in a script whose
only facts were generic). This flags such ungrounded specifics so the operator,
or a later gate, can catch the hallucination instead of shipping it.

Conservative by design — precision matters more than recall here:
  - only multi-word proper-noun phrases (2+ initial-capital words) and explicit
    Season/Patch/Version tokens are considered; everyday capitalised words and
    sentence-initial caps are filtered out via a common-word list,
  - ALL-CAPS acronyms (UFC, GTA, NBA) are ignored — usually known and safe,
  - a phrase is "grounded" if every distinctive (non-common) token appears
    anywhere in the facts corpus, so partial-name matches don't over-flag.

It FLAGS, never rewrites — stripping proper nouns would mangle the prose.
"""

from __future__ import annotations

import re

# Initial-capital word (excludes ALL-CAPS acronyms, which are usually known).
_CAP = r"[A-Z][a-z]+"
# Lowercase connectors allowed *inside* a single proper-noun phrase
# ("Need for Speed", "Lord of the Rings"). Deliberately excludes "and"/"vs"/etc.
# which join *separate* entities ("Emma Frost and Black Widow" → two phrases).
_CONNECT = r"(?:of|for|the)"
_PHRASE = re.compile(rf"{_CAP}(?:\s+(?:{_CONNECT}\s+)?{_CAP})+")

# Explicit version / season / patch specifics ("Season 8.5", "Patch 1.2").
_VERSION = re.compile(r"(?:Season|Patch|Version|Chapter|Act|Update)\s+[0-9][\w.]*", re.IGNORECASE)

# Common words that, alone, never make a phrase a "specific" worth verifying.
# Used both to drop all-common phrases and to pick out distinctive tokens.
_COMMON_WORDS = {
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
    "into",
    "over",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "his",
    "her",
    "their",
    "our",
    "your",
    "my",
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
    "may",
    "here",
    "there",
    "what",
    "why",
    "how",
    "when",
    "who",
    "which",
    "some",
    "many",
    "most",
    "more",
    "all",
    "new",
    "next",
    "now",
    "then",
    "drop",
    "let",
    "see",
    "players",
    "player",
    "fans",
    "game",
    "games",
    "season",
    "patch",
    "version",
    "update",
    "community",
    "meta",
    "thoughts",
    "comments",
    "yes",
    "no",
    "black",
    "white",
    "red",
    "blue",
    "green",
    "big",
    "best",
    "good",
    "bad",
    "another",
    "other",
}

_TOKEN = re.compile(r"[a-z0-9.]+")
# Distinctive mononyms common in sports scripts (LeBron, Kawhi, Giannis…).
_MONONYM = re.compile(r"\b([A-Z][A-Za-z']{3,})\b")
_SPORTS_CONTEXT_RE = re.compile(
    r"\b(?:nba|nfl|mlb|nhl|ufc|wnba|"
    r"traded|trade|trades|signing|signed|draft|offseason|playoffs|playoff|"
    r"championship|finals|roster|free agency|"
    r"lakers|celtics|knicks|bucks|heat|spurs|raptors|warriors|nets|76ers|sixers)\b",
    re.I,
)
_MONONYM_SKIP = _COMMON_WORDS | {
    "the",
    "this",
    "that",
    "who",
    "what",
    "when",
    "where",
    "why",
    "how",
    "but",
    "and",
    "for",
    "not",
    "are",
    "was",
    "has",
    "had",
    "his",
    "her",
    "they",
    "them",
    "our",
    "your",
    "tap",
    "nba",
    "ufc",
    "mlb",
    "nfl",
    "espn",
    "cbs",
    "let",
    "now",
    "then",
    "here",
    "there",
    "just",
    "still",
    "real",
    "bold",
    "free",
    "top",
    "new",
    "old",
    "big",
    "hot",
    "cold",
    "east",
    "west",
    "north",
    "south",
    "june",
    "july",
    "august",
    "january",
    "february",
    "march",
    "april",
    "may",
    "september",
    "october",
    "november",
    "december",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "meanwhile",
    "rookie",
    "bottom",
    "look",
    "teams",
    "squad",
    "paper",
    "award",
    "pivot",
    "clear",
    "leader",
    "favorite",
    "favourite",
    "watch",
    "built",
    "last",
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "early",
    "late",
    "current",
    "season",
    "series",
    "player",
    "support",
    "flex",
    "stats",
    "gaudy",
    "clutch",
    "moments",
    "prediction",
    "predictions",
    "contender",
    "contenders",
    "finals",
    "mid",
    "tier",
}


def _token_in_grounding(token: str, grounding: str) -> bool:
    """Whole-token match in the facts corpus (avoids substring false positives)."""
    if not token:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", grounding, re.I))


def _extract_mononyms(text: str, *, covered_spans: list[tuple[int, int]]) -> list[str]:
    """Single-word proper names not already part of a multi-word phrase."""
    if not _SPORTS_CONTEXT_RE.search(text or ""):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for match in _MONONYM.finditer(text or ""):
        start, end = match.span()
        if any(start >= s and end <= e for s, e in covered_spans):
            continue
        name = match.group(1)
        key = name.lower()
        if len(name) < 4 or key in _MONONYM_SKIP:
            continue
        if key not in seen:
            seen.add(key)
            out.append(name)
    return out


def extract_entities(text: str) -> list[str]:
    """Proper-noun phrases, mononyms, and explicit version tokens (order-preserving)."""
    out: list[str] = []
    seen: set[str] = set()
    covered: list[tuple[int, int]] = []
    for match in list(_PHRASE.finditer(text or "")) + list(_VERSION.finditer(text or "")):
        ent = match.group(0).strip()
        covered.append(match.span())
        key = ent.lower()
        if key not in seen:
            seen.add(key)
            out.append(ent)
    for ent in _extract_mononyms(text, covered_spans=covered):
        key = ent.lower()
        if key not in seen:
            seen.add(key)
            out.append(ent)
    return out


def _distinctive_tokens(entity: str) -> list[str]:
    return [t for t in _TOKEN.findall(entity.lower()) if t not in _COMMON_WORDS]


def specific_entities(text: str) -> list[str]:
    """Proper-noun entities in `text` that carry at least one distinctive token."""
    return [e for e in extract_entities(text) if _distinctive_tokens(e)]


def mentions(text: str, entity: str) -> bool:
    """True if every distinctive token of `entity` appears in `text` (case-insensitive)."""
    tokens = _distinctive_tokens(entity)
    low = (text or "").lower()
    return bool(tokens) and all(_token_in_grounding(t, low) for t in tokens)


def find_ungrounded_entities(script: str, grounding_text: str) -> list[str]:
    """
    Entities named in `script` whose distinctive tokens don't all appear in
    `grounding_text` (VERIFIED FACTS + key facts + brief + topic).

    Returns [] when everything specific in the script is backed by the facts.
    """
    grounding = (grounding_text or "").lower()
    ungrounded: list[str] = []
    for entity in extract_entities(script or ""):
        tokens = _distinctive_tokens(entity)
        if not tokens:
            continue  # all-common phrase ("The Community") — not a specific claim
        if all(_token_in_grounding(tok, grounding) for tok in tokens):
            continue  # every distinctive token is backed by the facts
        ungrounded.append(entity)
    return ungrounded
