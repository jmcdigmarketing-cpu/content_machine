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
# Hyphenated compounds count as ONE word: "Take-Two", "Spider-Man", "Jean-Luc".
_CAP = r"[A-Z][a-z]+(?:-[A-Z]?[a-z]+)*"
# Lowercase connectors allowed *inside* a single proper-noun phrase
# ("Need for Speed", "Lord of the Rings"). Deliberately excludes "and"/"vs"/etc.
# which join *separate* entities ("Emma Frost and Black Widow" → two phrases).
_CONNECT = r"(?:of|for|the)"
_PHRASE = re.compile(rf"{_CAP}(?:\s+(?:{_CONNECT}\s+)?{_CAP})+")

# A hyphenated proper noun standing alone ("Take-Two", "Spider-Man", "Nova-Strike").
# `_PHRASE` needs two space-separated capitals, and `_MONONYM` only fires in sports
# context, so before this a *fabricated* hyphenated name was invisible to grounding
# entirely — `find_ungrounded_entities("Nova-Strike launches soon.", facts)` returned
# []. A hyphenated compound is distinctive enough to verify on its own.
_HYPHEN_NAME = re.compile(r"\b[A-Z][a-z]+(?:-[A-Z][a-z]+)+\b")

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
    # Subordinating conjunctions and adverbs that open a sentence. Run 66 flagged
    # "If Netflix" as an unverified specific — `_CAP` matched sentence-initial "If",
    # and because "if" was absent here it counted as a *distinctive* token that had to
    # appear in the facts. It never does, so a clean script got a hallucination warning
    # and lost a grade. `_LEADING_STOPWORDS` below stops the phrase forming at all;
    # these entries also keep such words from being treated as distinctive anywhere.
    "if",
    "while",
    "because",
    "since",
    "though",
    "although",
    "unless",
    "until",
    "after",
    "before",
    "whether",
    "so",
    "yet",
    "both",
    "either",
    "neither",
    "once",
    "unlike",
    "despite",
    "meanwhile",
    "instead",
}

# A proper-noun phrase must not START on one of these. Sentence-initial capitalisation
# makes "If Netflix", "But Rockstar", "When Sony" look like two-word proper nouns; the
# entity actually worth verifying is the rest of the phrase.
#
# Deliberately a NARROW list of function words, not all of `_COMMON_WORDS`: that set also
# holds ordinary nouns and colours which are legitimately part of names, and trimming on
# it destroyed "Black Widow" -> "Widow" and "Season 8.5" -> "8.5". "The" is excluded too
# ("The Rock", "The Athletic" are real names).
_LEADING_STOPWORDS = frozenset(
    {
        "if",
        "when",
        "while",
        "because",
        "since",
        "though",
        "although",
        "unless",
        "until",
        "whether",
        "but",
        "and",
        "so",
        "yet",
        "then",
        "once",
        "unlike",
        "despite",
        "meanwhile",
        "instead",
        "what",
        "why",
        "how",
        "who",
        "which",
        "that",
        "this",
        "these",
        "those",
    }
)

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
    # Sentence-initial discourse adverbs. `_MONONYM` matches any capitalised word of
    # 4+ chars, so "Otherwise, we'll keep seeing…" was reported as an unsupported
    # specific in a live run — costing a real script 45 grounding points and a full
    # letter grade. These can never be a name.
    "otherwise",
    "however",
    "therefore",
    "instead",
    "basically",
    "meanwhile",
    "moreover",
    "furthermore",
    "besides",
    "regardless",
    "eventually",
    "suddenly",
    "clearly",
    "honestly",
    "frankly",
    "obviously",
    "either",
    "neither",
    "though",
    "although",
    "because",
    "since",
    "unless",
    "until",
    "while",
    "whether",
    "sure",
    "both",
    "here",
    "there",
    "then",
    "thats",
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


def _trim_leading_stopwords(entity: str) -> str:
    """Drop sentence-initial function words that only look like part of a proper noun.

    "If Netflix" -> "Netflix", "But Rockstar Games" -> "Rockstar Games". The capital is
    an artefact of starting a sentence, and reporting the whole phrase as the thing that
    failed verification is both wrong and confusing to read.
    """
    words = entity.split()
    while len(words) > 1 and words[0].lower() in _LEADING_STOPWORDS:
        words.pop(0)
    return " ".join(words)


def extract_entities(text: str) -> list[str]:
    """Proper-noun phrases, mononyms, and explicit version tokens (order-preserving)."""
    out: list[str] = []
    seen: set[str] = set()
    covered: list[tuple[int, int]] = []
    # Only phrase matches get trimmed — a _VERSION match is deliberately "Season 8.5",
    # and its leading word is the whole point of the pattern.
    phrase_spans = [m.span() for m in _PHRASE.finditer(text or "")]
    for match, trim in (
        [(m, True) for m in _PHRASE.finditer(text or "")]
        + [(m, False) for m in _VERSION.finditer(text or "")]
        + [(m, False) for m in _HYPHEN_NAME.finditer(text or "")]
    ):
        # A hyphenated name inside a longer phrase is already covered by it
        # ("Jean-Luc Picard" would otherwise also yield "Jean-Luc").
        start, end = match.span()
        if not trim and any(s <= start and end <= e for s, e in phrase_spans):
            continue
        ent = match.group(0).strip()
        if trim:
            ent = _trim_leading_stopwords(ent)
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
