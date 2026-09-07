"""Choose which collected facts ride into the prompt — rank, then fill.

Intake is uncapped: everything the operator pastes or scrapes is kept and written
to the vault. The *prompt* still has a budget, because operator facts ride in
every script and expansion call at roughly one token per four characters. What
changed after run 74 is how that budget is spent.

The old rule was insertion order plus `break` on overflow. Run 74 packed 54 facts
of which roughly fifteen were article furniture — "Below, you'll find everything
shown off…", "Check out the five biggest takeaways below.", "Note: All of these
details are compiled from various previews…" — while six wanted stars, the Slim
Jim minigame and the 80-hour playthrough sat in the tail that never fit. Raising
the ceiling would have packed more furniture. Ranking is what fixes it.

Three rules keep ground truth safe:

  1. **Operator-typed facts are pinned.** `TIER_OPERATOR` lines are never ranked
     out — decisions §4 makes them the highest ground truth in the system, and a
     scorer demoting the thing the operator typed by hand is a bug, not a feature.
  2. **Scaffolding is penalised, not blacklisted.** A boilerplate-shaped line that
     still carries a real number survives; only content-free furniture sinks.
  3. **Every exclusion carries a reason.** A silent drop of ground truth is the
     worst failure this module can have.

Relevance reuses `core.vault_relevance.score_vault_fact` (additive, banded,
explainable) and recency reuses `core.fact_store.freshness_bonus`. The two terms
added here — specificity and novelty — exist because neither of those answers the
question this module actually asks: not "is this line about the topic?" but "of
the facts about this topic, which ones are worth the budget?".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from core.fact_store import TIER_LINK, TIER_OPERATOR, FactRecord, freshness_bonus
from core.logging import get_logger
from core.operator_facts import key_fact_split_width, max_operator_key_facts, split_at_sentences

logger = get_logger("core.fact_selection")

# Recency is weighted heavily by design (operator call, 2026-08-29): a stale fact
# about a live story is worse than no fact, because the model states it flatly.
#
# Relevance is deliberately the *smallest* weight. `score_vault_fact` measures how
# much a line echoes the existing signal corpus, which is the right question for a
# vault note ("is this even about the topic?") and the wrong one here: every line
# in this pool came from an article the operator chose for this topic, so it is
# on-topic by construction. Measured on run 74's own facts, corpus-echo scored the
# Slim Jim carjacking mechanic at 0.03 — the single most useful detail in the
# article — purely because the signals had not already reported it. Relevance
# stays as a floor against genuinely off-subject lines; `novelty` is what rewards
# a fact for adding something the signals do not already carry.
_WEIGHT_RELEVANCE = 0.20
_WEIGHT_RECENCY = 0.35
_WEIGHT_SPECIFICITY = 0.20
_WEIGHT_NOVELTY = 0.25
# Applied as a subtraction, so it can outweigh a scaffolding line's topic-word
# density — that density is exactly why furniture used to score well.
_WEIGHT_SCAFFOLDING = 0.45

# `freshness_bonus` returns 0..0.45 over a 90-day window; rescale to 0..1.
_MAX_FRESHNESS = 0.45
# An undated fact is unknown, not old. Most pasted facts carry no date, and
# sending them to the floor would rank a paste below a stale vault note.
_UNDATED_RECENCY = 0.5

# Article furniture: lines whose subject is the article rather than the story.
_SCAFFOLDING_MARKERS = (
    "you will find",
    "you'll find",
    "listed below",
    " below.",
    " below:",
    "check out",
    "note:",
    "compiled from",
    "we have gone through",
    "we've gone through",
    "put together a roundup",
    "roundup of everything",
    "everything shown off",
    "everything announced",
    "all the news",
    "and more from",
    "on this page",
    "in this article",
    "keep reading",
    "scroll down",
    "read more",
    "just a reminder",
    "here are some things we learned",
    "complete guide to",
)

# A standalone multi-digit number. Deliberately not `\d`: "GTA 6" and "GTA 5" are
# titles, not evidence, and counting them made every furniture line look specific.
_HARD_NUMBER = re.compile(r"\b\d{2,}\b")
_ANY_NUMBER = re.compile(r"\b\d[\d,.]*\b")
# #648: the article as subject, not a hand-built phrase list. "this wrap-up
# covers…" has no "you'll find" and still is furniture.
_ARTICLE_DEIXIS = re.compile(
    r"\b(?:this|the)\s+(?:article|page|wrap-?up|round[- ]?up|post|write-?up|"
    r"listicle|piece|roundup)\b",
    re.I,
)


@dataclass(frozen=True)
class FactSelectionDrop:
    """One fact that did not make the prompt, and why."""

    claim: str
    reason: str
    score: float = 0.0


@dataclass
class _Entry:
    index: int
    record: FactRecord
    chunks: list[str]
    cost: int
    score: float
    pinned: bool


def scaffolding_penalty(text: str) -> float:
    """0..1 — how much of this line is about the article rather than the story.

    Penalty, never a blacklist: a furniture-shaped line carrying a hard number
    ("Below you will find all 150 new details") is still evidence, and halving its
    penalty lets it compete instead of vanishing.
    """
    body = (text or "").strip().lower()
    if not body:
        return 0.0
    hits = sum(1 for marker in _SCAFFOLDING_MARKERS if marker in body)
    deixis = bool(_ARTICLE_DEIXIS.search(body))
    if not hits and not deixis:
        return 0.0
    base = min(1.0, 0.5 + 0.2 * (max(hits, 1) - 1)) if hits else 0.5
    evidence = 0.5 if _HARD_NUMBER.search(body) else 0.0
    return round(base * (1.0 - evidence), 4)


def _specificity(text: str) -> float:
    """0..1 — density of the things that make a fact usable: numbers and names."""
    from core.fact_grounding import specific_entities

    body = (text or "").strip()
    if not body:
        return 0.0
    numbers = len(_ANY_NUMBER.findall(body))
    entities = len(specific_entities(body))
    return round(min(1.0, 0.2 * numbers + 0.12 * entities), 4)


def _novelty(text: str, corpus: str) -> float:
    """0..1 — share of this fact's named entities the corpus does not already have.

    Information gain, not similarity. A fact that repeats the signals is redundant;
    a fact that names something new is the reason the operator pasted the article.
    """
    from core.fact_grounding import mentions, specific_entities

    entities = specific_entities(text or "")
    if not entities:
        return 0.5  # no names to judge — neutral, same as an undated fact
    unseen = [entity for entity in entities if not mentions(corpus or "", entity)]
    return round(len(unseen) / len(entities), 4)


def _recency(record: FactRecord, today: date) -> float:
    if record.verified_at is None:
        return _UNDATED_RECENCY
    return round(freshness_bonus(record.verified_at, today=today) / _MAX_FRESHNESS, 4)


def _relevance(record: FactRecord, *, topic: str, corpus: str) -> float:
    if not (topic or corpus):
        return 0.5  # nothing to score against — neutral, not zero
    try:
        from core.vault_relevance import score_vault_fact

        return float(
            score_vault_fact(
                topic=topic,
                corpus=corpus,
                bullet=record.claim,
                note_context="",
                tier=record.tier,
            ).score
        )
    except Exception as exc:  # a scorer failure must never drop ground truth
        logger.debug("relevance scoring unavailable for %r: %s", record.claim[:60], exc)
        return 0.5


def _composite(
    record: FactRecord,
    *,
    topic: str,
    corpus: str,
    today: date,
    weights: dict[str, float] | None = None,
) -> float:
    rel = (weights or {}).get("relevance", _WEIGHT_RELEVANCE)
    rec = (weights or {}).get("recency", _WEIGHT_RECENCY)
    spec = (weights or {}).get("specificity", _WEIGHT_SPECIFICITY)
    nov = (weights or {}).get("novelty", _WEIGHT_NOVELTY)
    scaf = (weights or {}).get("scaffolding", _WEIGHT_SCAFFOLDING)
    score = (
        rel * _relevance(record, topic=topic, corpus=corpus)
        + rec * _recency(record, today)
        + spec * _specificity(record.claim)
        + nov * _novelty(record.claim, corpus)
        - scaf * scaffolding_penalty(record.claim)
    )
    return round(max(0.0, min(1.0, score)), 4)


def select_facts_for_prompt(
    records: list[FactRecord] | None,
    *,
    topic: str = "",
    corpus: str = "",
    budget: int,
    line_cap: int | None = None,
    width: int | None = None,
    today: date | None = None,
    weights: dict[str, float] | None = None,
) -> tuple[list[str], list[FactSelectionDrop]]:
    """Prompt lines chosen by score, emitted in intake order, plus what was cut.

    Selection is by rank; *presentation* is by the order the operator gave them,
    so the block still reads the way they built it.

    A fact that does not fit is skipped, not `break`-ed on: a short high-value fact
    after a long one still gets its place. That alone recovers several facts per
    run compared with the old first-N-then-stop rule.
    """
    if not records:
        return [], []
    today = today or date.today()
    width = width or key_fact_split_width()
    line_cap = line_cap if line_cap is not None else max_operator_key_facts()

    entries: list[_Entry] = []
    for index, record in enumerate(records):
        chunks = split_at_sentences(record.claim, width)
        if not chunks:
            continue
        pinned = (record.tier or "").strip().lower() == TIER_OPERATOR
        entries.append(
            _Entry(
                index=index,
                record=record,
                chunks=chunks,
                cost=sum(len(chunk) + 2 for chunk in chunks),
                # Pinned facts sort ahead of everything; the value is an ordering
                # token, not a claim that the operator's line scored 2.0.
                score=2.0
                if pinned
                else _composite(record, topic=topic, corpus=corpus, today=today, weights=weights),
                pinned=pinned,
            )
        )

    ranked = sorted(entries, key=lambda e: (0 if e.pinned else 1, -e.score, e.index))
    chosen: list[_Entry] = []
    drops: list[FactSelectionDrop] = []
    used = 0
    lines = 0
    for entry in ranked:
        if lines + len(entry.chunks) > line_cap:
            drops.append(
                FactSelectionDrop(
                    entry.record.claim,
                    f"line cap {line_cap} reached (raise MAX_OPERATOR_KEY_FACTS)",
                    entry.score,
                )
            )
            continue
        if used + entry.cost > budget:
            drops.append(
                FactSelectionDrop(
                    entry.record.claim,
                    (
                        f"outranked at the {budget}-char budget (score {entry.score:.2f}"
                        + (
                            ", article scaffolding"
                            if scaffolding_penalty(entry.record.claim) > 0
                            else ""
                        )
                        + ")"
                    ),
                    entry.score,
                )
            )
            continue
        chosen.append(entry)
        used += entry.cost
        lines += len(entry.chunks)

    chosen.sort(key=lambda e: e.index)
    out = [chunk for entry in chosen for chunk in entry.chunks]
    if drops:
        logger.info("%d fact(s) held back from the prompt (%d packed)", len(drops), len(out))
    return out, drops


def select_headless_facts(
    facts: list[str] | None,
    *,
    topic: str = "",
    corpus: str = "",
    typed: list[str] | None = None,
    budget: int | None = None,
    line_cap: int | None = None,
    today: date | None = None,
) -> list[str]:
    """Rank a facts-file / --fact pool the same way the interactive prompt does.

    File lines are treated as link-extracted article text (ranked, scaffolding
    sinks). Repeated ``--fact`` lines are pinned as operator-typed (decisions §4).
    """
    from core.operator_facts import (
        dedupe_facts,
        dedupe_key,
        operator_key_fact_char_budget,
    )

    collected = dedupe_facts(list(facts or []))
    if not collected:
        return []
    typed_keys = {dedupe_key(line) for line in (typed or []) if line}
    today = today or date.today()
    records = [
        FactRecord(
            claim=claim,
            tier=TIER_OPERATOR if dedupe_key(claim) in typed_keys else TIER_LINK,
            verified_at=today if dedupe_key(claim) in typed_keys else None,
        )
        for claim in collected
    ]
    kept, _drops = select_facts_for_prompt(
        records,
        topic=topic,
        corpus=corpus,
        budget=budget if budget is not None else operator_key_fact_char_budget(),
        line_cap=line_cap,
        today=today,
    )
    return kept


# #647: measured against two fixture topics (run-74 GTA strings + UFC), never the
# operator store. Current split beat insertion order and equal weights → hold.
WEIGHT_MEASUREMENT = {
    "verdict": "held",
    "split": {
        "recency": _WEIGHT_RECENCY,
        "novelty": _WEIGHT_NOVELTY,
        "relevance": _WEIGHT_RELEVANCE,
        "specificity": _WEIGHT_SPECIFICITY,
        "scaffolding": _WEIGHT_SCAFFOLDING,
    },
}


def _pack_quality(kept: list[str], detail: list[str], scaffolding: list[str]) -> int:
    packed = " ".join(kept)
    hits = sum(1 for line in detail if line in packed)
    furniture = sum(1 for line in scaffolding if line in packed)
    return hits - furniture


def measure_weight_split(
    cases: list[dict[str, Any]],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Compare the shipped split to insertion order and equal weights.

    Each case is a dict of topic/corpus/claims/detail/scaffolding/budget.
    Quality = (gold detail lines packed) minus (scaffolding lines packed).
    """
    today = today or date.today()
    equal = {
        "relevance": 0.25,
        "recency": 0.25,
        "specificity": 0.25,
        "novelty": 0.25,
        "scaffolding": _WEIGHT_SCAFFOLDING,
    }
    insertion = {
        "relevance": 0.0,
        "recency": 0.0,
        "specificity": 0.0,
        "novelty": 0.0,
        "scaffolding": 0.0,
    }
    current_q = insertion_q = equal_q = 0
    for case in cases:
        records = [
            FactRecord(claim=claim, tier=TIER_LINK, verified_at=today)
            for claim in (case.get("claims") or [])
        ]
        budget = int(case.get("budget") or 400)
        topic = str(case.get("topic") or "")
        corpus = str(case.get("corpus") or "")
        detail = list(case.get("detail") or [])
        scaffolding = list(case.get("scaffolding") or [])
        current, _ = select_facts_for_prompt(
            records, topic=topic, corpus=corpus, budget=budget, today=today, line_cap=500
        )
        ins, _ = select_facts_for_prompt(
            records,
            topic=topic,
            corpus=corpus,
            budget=budget,
            today=today,
            line_cap=500,
            weights=insertion,
        )
        eq, _ = select_facts_for_prompt(
            records,
            topic=topic,
            corpus=corpus,
            budget=budget,
            today=today,
            line_cap=500,
            weights=equal,
        )
        current_q += _pack_quality(current, detail, scaffolding)
        insertion_q += _pack_quality(ins, detail, scaffolding)
        equal_q += _pack_quality(eq, detail, scaffolding)
    verdict = "held" if current_q > insertion_q and current_q >= equal_q else "retune"
    return {
        "verdict": verdict,
        "current_quality": current_q,
        "insertion_quality": insertion_q,
        "equal_quality": equal_q,
    }
