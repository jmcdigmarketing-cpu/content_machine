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
}

_TOKEN = re.compile(r"[a-z0-9.]+")


def extract_entities(text: str) -> list[str]:
    """Proper-noun phrases + explicit version tokens found in text (order-preserving)."""
    out: list[str] = []
    seen: set[str] = set()
    for match in list(_PHRASE.finditer(text)) + list(_VERSION.finditer(text)):
        ent = match.group(0).strip()
        key = ent.lower()
        if key not in seen:
            seen.add(key)
            out.append(ent)
    return out


def _distinctive_tokens(entity: str) -> list[str]:
    return [t for t in _TOKEN.findall(entity.lower()) if t not in _COMMON_WORDS]


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
        if all(tok in grounding for tok in tokens):
            continue  # every distinctive token is backed by the facts
        ungrounded.append(entity)
    return ungrounded
