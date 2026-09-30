"""A confidence per fact (#548): tier, relevance, age and corroboration in one number.

Each fact carried its provenance tier (`store.TIER_WEIGHTS`) and vault lines a relevance
score (`core/vault/relevance`), but nothing combined them - a year-old single-source vault
line and a corroborated link line from this week looked alike. `fact_confidence` is:

    tier weight x relevance factor x age factor + corroboration bonus, clipped to 0..1

- relevance factor = 0.5 + 0.5 x relevance (unknown relevance is neutral: 1.0);
- age factor = 1.0 up to 90 days, 0.85 up to a year, 0.7 beyond (undated: 1.0);
- corroboration bonus = 0.1 per other source saying the same thing, at most two.

Context-tier lines stay at 0 (they are topic evidence, never facts). This ranks the
facts room (#860) and is printed beside vault lines; it gates nothing - which facts
reach the script is decided exactly as before.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from apis.topic_tokens import content_tokens
from core.facts.store import TIER_CONTEXT, tier_weight

_SHARED_TOKENS = 3  # tokens two lines must share to say the same thing


@dataclass
class FactConfidence:
    value: float
    label: str  # high | medium | low
    parts: dict[str, float] = field(default_factory=dict)


def _age_factor(age_days: int | None) -> float:
    if age_days is None or age_days <= 90:
        return 1.0
    return 0.85 if age_days <= 365 else 0.7


def fact_confidence(
    *,
    tier: str,
    relevance: float | None = None,
    corroborations: int = 0,
    age_days: int | None = None,
    trust: float = 1.0,
) -> FactConfidence:
    """0..1 with its four parts. Pure; never raises on odd input. `trust` (#342) scales
    the tier part for a source the corrections have demoted."""
    base = 0.0 if (tier or "").strip().lower() == TIER_CONTEXT else tier_weight(tier)
    base *= max(0.0, min(1.0, float(trust)))
    rel = 1.0 if relevance is None else 0.5 + 0.5 * max(0.0, min(1.0, float(relevance)))
    age = _age_factor(age_days)
    bonus = 0.0 if base == 0.0 else 0.1 * max(0, min(2, int(corroborations)))
    value = round(max(0.0, min(1.0, base * rel * age + bonus)), 2)
    label = "high" if value >= 0.7 else "medium" if value >= 0.45 else "low"
    return FactConfidence(
        value=value,
        label=label,
        parts={"tier": base, "relevance": rel, "age": age, "corroboration": bonus},
    )


def corroboration_counts(lines: list[tuple[str, str]]) -> list[int]:
    """For each (line, source): how many *other* sources carry a line sharing at least
    three content tokens with it (`apis.topic_tokens.content_tokens`)."""
    tokens = [set(content_tokens(text)) for text, _source in lines]
    counts: list[int] = []
    for i, (_text, source) in enumerate(lines):
        others = {
            other_source
            for j, (_t, other_source) in enumerate(lines)
            if j != i and other_source != source and len(tokens[i] & tokens[j]) >= _SHARED_TOKENS
        }
        counts.append(len(others))
    return counts


def record_confidence(
    record: Any, *, corroborations: int = 0, today: date | None = None
) -> FactConfidence:
    """`fact_confidence` for a `store.FactRecord` (tier, relevance score, verified date,
    and its source's trust)."""
    from core.facts.trust import source_factor

    verified = getattr(record, "verified_at", None)
    age = ((today or date.today()) - verified).days if isinstance(verified, date) else None
    score = getattr(record, "relevance_score", None)
    return fact_confidence(
        tier=str(getattr(record, "tier", "") or ""),
        relevance=float(score) if isinstance(score, int | float) else None,
        corroborations=corroborations,
        age_days=age,
        trust=source_factor(
            str(getattr(record, "trust_source", "") or getattr(record, "source_url", "") or "")
        ),
    )


def confidence_suffix(record: Any) -> str:
    """` · conf 0.62` for the key-facts vault review line."""
    try:
        return f" · conf {record_confidence(record).value:.2f}"
    except Exception:
        return ""


def selection_confidences(records: list[Any]) -> list[dict[str, Any]]:
    """#911: `{claim, tier, value, label}` per collected fact, for the run's features.

    Corroboration counts other sources in the same selection (a page's URL, the vault
    note, or the tier when neither is known).
    """
    rows = [r for r in records or [] if getattr(r, "claim", None)]
    sources = [
        (
            str(r.claim),
            str(getattr(r, "source_url", "") or getattr(r, "note_path", "") or r.tier or ""),
        )
        for r in rows
    ]
    counts = corroboration_counts(sources)
    out: list[dict[str, Any]] = []
    for record, n in zip(rows, counts, strict=True):
        conf = record_confidence(record, corroborations=n)
        out.append(
            {
                "claim": str(record.claim),
                "tier": str(getattr(record, "tier", "") or ""),
                "value": conf.value,
                "label": conf.label,
            }
        )
    return out


def confidence_summary(items: list[dict[str, Any]] | None) -> str | None:
    """`6 high, 3 medium, 1 low; lowest 0.36 "..."` - None when nothing was recorded."""
    rows = [i for i in items or [] if isinstance(i, dict) and "value" in i]
    if not rows:
        return None
    counts = {
        label: sum(1 for i in rows if i.get("label") == label)
        for label in ("high", "medium", "low")
    }
    lowest = min(rows, key=lambda i: float(i.get("value") or 0.0))
    claim = str(lowest.get("claim") or "")
    claim = claim if len(claim) <= 70 else claim[:69] + "…"
    return (
        f"{counts['high']} high, {counts['medium']} medium, {counts['low']} low; "
        f'lowest {float(lowest.get("value") or 0.0):.2f} "{claim}"'
    )
