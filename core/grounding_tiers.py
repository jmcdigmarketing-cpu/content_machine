"""Tiered grounding corpus (Pillar 3 — Fact Engine 2.0).

The audit finding this fixes: operator paste, link scrapes, web snippets,
structured API data, and YouTube titles/descriptions all shared ONE
undifferentiated grounding corpus — so a script's trade claim could "ground"
against a competitor's video title, which the system's own prompt says is
"NOT facts about specific events".

``build_tiered_corpus`` tags every corpus line with a provenance tier
(``operator | signal | web | brief | context`` — see ``core/fact_store.py``),
keeping the flat ``full_text`` byte-identical to the old grounding string so
`find_ungrounded_entities` / trade validation behave exactly as before.

Two lint checks read the tiers (both WARN, never block or rewrite):

  - ``context_grounded_entities`` — script specifics that pass token grounding
    ONLY because of a YouTube title/description line (the exact leak above).
  - ``high_stakes_low_tier`` — trade/result/record claims whose entities are
    backed only by web/brief/context text, not operator facts or structured
    API data (Tapology, ESPN live/final, stats): "verify or add a key fact".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.fact_grounding import mentions, specific_entities
from core.fact_store import (
    TIER_BRIEF,
    TIER_CONTEXT,
    TIER_OPERATOR,
    TIER_SIGNAL,
    TIER_WEB,
)

# YouTube sections are context-only (topic evidence, not facts). Shared with
# content_engine._split_facts_block — defined here so both read one list.
YOUTUBE_SECTION_HEADERS = (
    "YouTube — real video titles",
    "YouTube video descriptions",
    "YouTube market titles",
    "YouTube competitor performance",
)

# signal_facts section prefix → tier. First match wins; unknown prefixes stay
# on the `signal` tier (structured-but-unclassified beats false confidence).
_SECTION_TIERS: tuple[tuple[str, str], ...] = tuple(
    [(h, TIER_CONTEXT) for h in YOUTUBE_SECTION_HEADERS]
    + [
        ("Live web search", TIER_WEB),
        ("News headlines", TIER_WEB),
        ("News API", TIER_WEB),
        ("Blog/RSS", TIER_WEB),
        ("RSS headlines", TIER_WEB),
        ("MMA RSS", TIER_WEB),
        ("UFC/MMA headlines", TIER_WEB),
        ("Reddit community", TIER_WEB),
        ("Twitter/X", TIER_WEB),
        ("TikTok trending", TIER_WEB),
        ("Extracted facts", TIER_WEB),  # LLM-extracted from the mixed sources above
        ("Tapology", TIER_SIGNAL),
        ("Card:", TIER_SIGNAL),
        ("ESPN live/final", TIER_SIGNAL),
        ("Stats:", TIER_SIGNAL),
        ("Game database", TIER_SIGNAL),
        ("RAWG", TIER_SIGNAL),
        ("sports teams (API)", TIER_SIGNAL),
    ]
)

# Continuation lines (bullets / indents) inherit the current section's tier.
_CONTINUATION = re.compile(r"^(?:\s{2,}|[-•→]\s|\s+[•→])")

# Claims that must not ride on low-tier sources: roster moves, results, titles.
_HIGH_STAKES_RE = re.compile(
    r"\b(?:traded?|dealt|shipped|acquired?|signed|waived|released|drafted|"
    r"defeated|beat|beats|knocked\s+out|ko'?d|tko'?d|submitted|"
    r"champion|title|record\s+of|undefeated)\b",
    re.I,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

_MAX_WARNINGS = 8


@dataclass
class TieredCorpus:
    """The grounding corpus with a provenance tier per line."""

    lines: list[tuple[str, str]] = field(default_factory=list)  # (tier, line)
    full_text: str = ""  # exactly the legacy grounding string

    def text_for_tiers(self, tiers: set[str]) -> str:
        return "\n".join(line for tier, line in self.lines if tier in tiers)

    @property
    def factual_text(self) -> str:
        """Everything except context-only lines (YouTube titles/descriptions)."""
        return "\n".join(line for tier, line in self.lines if tier != TIER_CONTEXT)

    @property
    def trusted_text(self) -> str:
        """Operator facts + structured API data — what high-stakes claims need."""
        return self.text_for_tiers({TIER_OPERATOR, TIER_SIGNAL})

    def tier_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for tier, line in self.lines:
            if line.strip():
                counts[tier] = counts.get(tier, 0) + 1
        return counts


def _tag_signal_facts(signal_facts: str) -> list[tuple[str, str]]:
    """Tier per line of the enriched signal-facts block, section-aware."""
    tagged: list[tuple[str, str]] = []
    current = TIER_SIGNAL
    for line in (signal_facts or "").splitlines():
        stripped = line.strip()
        if stripped and not _CONTINUATION.match(line):
            # Top-level line: a known section header switches the tier;
            # anything else is a standalone structured line (signal tier).
            current = TIER_SIGNAL
            for prefix, tier in _SECTION_TIERS:
                if stripped.startswith(prefix):
                    current = tier
                    break
        tagged.append((current, line))
    return tagged


def build_tiered_corpus(
    *,
    signal_facts: str,
    brief_block: str = "",
    topic: str = "",
    seed_topic: str = "",
    key_facts: list[str] | None = None,
) -> TieredCorpus:
    """Assemble the grounding corpus with per-line tiers.

    ``full_text`` reproduces the legacy join (signal facts, brief, topic, seed
    topic, then key facts) so downstream token grounding and per-line trade
    validation see the identical corpus they always did.
    """
    corpus = TieredCorpus()
    corpus.lines.extend(_tag_signal_facts(signal_facts))
    for line in (brief_block or "").splitlines():
        corpus.lines.append((TIER_BRIEF, line))
    corpus.lines.append((TIER_BRIEF, topic or ""))
    corpus.lines.append((TIER_BRIEF, seed_topic or ""))
    for fact in key_facts or []:
        corpus.lines.append((TIER_OPERATOR, fact))

    corpus.full_text = "\n".join(
        [signal_facts or "", brief_block or "", topic or "", seed_topic or "", *(key_facts or [])]
    )
    return corpus


def context_grounded_entities(script: str, corpus: TieredCorpus) -> list[str]:
    """Script specifics grounded ONLY by context lines (YouTube titles/descriptions).

    These pass `find_ungrounded_entities` against the full corpus, but the only
    "facts" backing them are competitor titles — the leak the tier layer exists
    to catch.
    """
    factual = corpus.factual_text
    out: list[str] = []
    for entity in specific_entities(script or ""):
        if mentions(corpus.full_text, entity) and not mentions(factual, entity):
            out.append(entity)
    return out


def high_stakes_low_tier(script: str, corpus: TieredCorpus) -> list[str]:
    """Warnings for trade/result/record claims backed only by low-tier sources.

    A high-stakes sentence's entities must ground against operator facts or
    structured API data (Tapology, ESPN, stats). Entities grounded only in
    web/news/community/brief/context text get a "verify" warning; entities not
    grounded anywhere are token grounding's job and are skipped here.
    """
    trusted = corpus.trusted_text
    warnings: list[str] = []
    flagged: set[str] = set()
    for sentence in _SENTENCE_SPLIT.split(script or ""):
        if not _HIGH_STAKES_RE.search(sentence):
            continue
        for entity in specific_entities(sentence):
            key = entity.lower()
            if key in flagged:
                continue
            if not mentions(corpus.full_text, entity):
                continue  # fully ungrounded — already flagged by token grounding
            if mentions(trusted, entity):
                continue
            flagged.add(key)
            warnings.append(
                f"High-stakes claim about '{entity}' is backed only by unverified "
                f"sources (web/news/titles) - verify it or add an operator key fact."
            )
    return warnings


def tier_warnings_for_script(script: str, corpus: TieredCorpus) -> list[str]:
    """All tier-layer warnings for a finished script (capped, deduped)."""
    context_only = set(context_grounded_entities(script, corpus))
    warnings = [
        f"'{entity}' only grounds when YouTube titles/descriptions are counted "
        f"(context, not facts) - treat as unverified."
        for entity in sorted(context_only)
    ]
    warnings.extend(
        w
        for w in high_stakes_low_tier(script, corpus)
        # A context-grounded entity already got the sharper warning above.
        if not any(f"'{e}'" in w for e in context_only)
    )
    return warnings[:_MAX_WARNINGS]
