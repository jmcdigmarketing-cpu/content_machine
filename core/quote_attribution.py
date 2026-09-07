"""#338. Quoted speech must map to a source that names the speaker.

Deterministic: no extra LLM call. Short titles like "GTA 6" are skipped.
Nested quotes are a known gap (odd pairing / inner spans).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SPEECH = re.compile(
    r"\b(said|says|told|tells|according to|announced|announces|"
    r"claimed|claims|asked|replied|added)\b",
    re.I,
)
_QUOTED = re.compile(r'"([^"]{8,})"')
_NAME = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")


@dataclass(frozen=True)
class FlaggedQuote:
    quote: str
    speaker: str
    reason: str


@dataclass
class QuoteAttribution:
    flagged: list[FlaggedQuote] = field(default_factory=list)
    known_gap: bool = False

    @property
    def flagged_count(self) -> int:
        return len(self.flagged)

    def to_dict(self) -> dict:
        return {
            "flagged_count": self.flagged_count,
            "known_gap": self.known_gap,
            "flagged": [
                {"quote": item.quote, "speaker": item.speaker, "reason": item.reason}
                for item in self.flagged
            ],
        }


def check_quote_attribution(script: str, facts: str) -> QuoteAttribution:
    text = script or ""
    corpus = facts or ""
    known_gap = text.count('"') >= 4 or ("“" in text and text.count("“") != text.count("”"))
    flagged: list[FlaggedQuote] = []
    facts_cf = corpus.casefold()
    for match in _QUOTED.finditer(text):
        quote = match.group(1).strip()
        prefix = text[max(0, match.start() - 140) : match.start()]
        if _is_title(quote, prefix):
            continue
        speaker = _speaker_from_prefix(prefix)
        verb = bool(_SPEECH.search(prefix[-80:]))
        if not verb:
            if _looks_spoken_sentence(quote):
                flagged.append(FlaggedQuote(quote=quote, speaker="", reason="unattributed quote"))
            continue
        if not speaker:
            flagged.append(FlaggedQuote(quote=quote, speaker="", reason="no speaker named"))
            continue
        if speaker.casefold() not in facts_cf:
            flagged.append(
                FlaggedQuote(quote=quote, speaker=speaker, reason="speaker not in facts")
            )
            continue
        if not _quote_in_facts(quote, corpus):
            flagged.append(FlaggedQuote(quote=quote, speaker=speaker, reason="quote not in facts"))
    return QuoteAttribution(flagged=flagged, known_gap=known_gap)


def _is_title(quote: str, prefix: str) -> bool:
    words = [w for w in re.findall(r"[A-Za-z0-9']+", quote) if w]
    if len(words) <= 4 and not quote.rstrip().endswith((".", "!", "?")):
        if not _SPEECH.search(prefix[-80:]):
            return True
    return False


def _looks_spoken_sentence(quote: str) -> bool:
    return quote.rstrip().endswith((".", "!", "?")) or len(quote.split()) >= 6


def _speaker_from_prefix(prefix: str) -> str:
    window = prefix[-80:]
    verb = _SPEECH.search(window)
    if not verb:
        return ""
    before = window[: verb.start()]
    names = _NAME.findall(before)
    return names[-1].strip() if names else ""


def _quote_in_facts(quote: str, facts: str) -> bool:
    compact = re.sub(r"\s+", " ", quote).strip().casefold().strip('"')
    hay = re.sub(r"\s+", " ", facts).casefold()
    if compact and compact in hay:
        return True
    tokens = [t for t in re.findall(r"[a-z0-9']+", compact) if len(t) > 2]
    if len(tokens) < 3:
        return bool(tokens) and all(t in hay for t in tokens)
    hits = sum(1 for t in tokens if t in hay)
    return hits / len(tokens) >= 0.7
