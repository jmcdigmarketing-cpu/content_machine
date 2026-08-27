"""Structured fact model — provenance tiers, freshness, and expiry (Pillar 3).

The audit finding this fixes: facts were flat strings with no provenance or
TTL — operator paste, link scrapes, web snippets, and YouTube descriptions all
looked identical to grounding, and a stale "champion"/roster note ranked the
same as one verified yesterday.

This module is the pure model + math layer (no I/O):

  - ``FactRecord`` — ``{claim, tier, source_url, verified_at, expires}``.
  - Provenance tiers with trust weights (operator > link > web > signal >
    vault > brief; ``context`` = YouTube titles/descriptions, never trusted).
  - Freshness scoring: a dated fact's rank bonus decays linearly to zero over
    ``_FRESHNESS_WINDOW_DAYS``; evergreen notes don't decay; expired facts are
    dropped by the reader.

Vault notes carry the metadata as frontmatter (``verified_at:``, ``expires:``,
``tier:``, ``source:``) — no plugin needed. ``core/obsidian_facts.py`` parses
notes into records and folds ``rank_bonus`` into its topic-overlap ranking, so
fresh, high-provenance facts surface first and stale ones age out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

TIER_OPERATOR = "operator"
TIER_LINK = "link"
TIER_WEB = "web"
TIER_SIGNAL = "signal"
TIER_VAULT = "vault"
TIER_BRIEF = "brief"
TIER_CONTEXT = "context"  # YouTube titles/descriptions — topic evidence, not facts

# Trust weight per provenance tier (0..1). Context is deliberately 0 — it must
# never lend grounding weight to a factual claim.
TIER_WEIGHTS: dict[str, float] = {
    TIER_OPERATOR: 1.0,
    TIER_LINK: 0.85,
    TIER_WEB: 0.6,
    TIER_SIGNAL: 0.55,
    TIER_VAULT: 0.5,
    TIER_BRIEF: 0.4,
    TIER_CONTEXT: 0.0,
}

# A dated fact's freshness bonus decays to zero over this many days.
_FRESHNESS_WINDOW_DAYS = 90
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def parse_iso_date(raw: str | None) -> date | None:
    """Tolerant YYYY-MM-DD parse (frontmatter values may carry extra text)."""
    if not raw:
        return None
    m = _DATE_RE.search(str(raw))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


@dataclass(frozen=True)
class FactRecord:
    """One fact with provenance — the structured replacement for a bare string."""

    claim: str
    tier: str = TIER_VAULT
    source_url: str = ""
    verified_at: date | None = None
    expires: date | None = None
    note_path: str = ""
    # Candidate 329 P0: relevant on token evidence but with no franchise anchor shared
    # with the topic, so subject identity is unproven either way. Kept and surfaced for
    # review rather than dropped — a silent exclusion is worse than a visible guess,
    # because the operator never learns their own note was withheld.
    uncertain: bool = False

    def is_expired(self, today: date | None = None) -> bool:
        if self.expires is None:
            return False
        return self.expires < (today or date.today())

    def age_days(self, today: date | None = None) -> int | None:
        if self.verified_at is None:
            return None
        return max(0, ((today or date.today()) - self.verified_at).days)

    def to_dict(self) -> dict[str, str]:
        return {
            "claim": self.claim,
            "tier": self.tier,
            "source_url": self.source_url,
            "verified_at": self.verified_at.isoformat() if self.verified_at else "",
            "expires": self.expires.isoformat() if self.expires else "",
        }


def tier_weight(tier: str) -> float:
    return TIER_WEIGHTS.get((tier or "").strip().lower(), TIER_WEIGHTS[TIER_VAULT])


def freshness_bonus(verified_at: date | None, *, today: date | None = None) -> float:
    """0..0.45 rank bonus for recency; undated facts are neutral (0)."""
    if verified_at is None:
        return 0.0
    age = max(0, ((today or date.today()) - verified_at).days)
    return round(max(0.0, 0.45 * (1 - age / _FRESHNESS_WINDOW_DAYS)), 4)


def rank_bonus(
    *,
    tier: str = TIER_VAULT,
    verified_at: date | None = None,
    today: date | None = None,
) -> float:
    """Provenance + freshness bonus — strictly below 1.0 by construction.

    Topic overlap scores in whole tokens (integers), so keeping this under one
    token means an on-topic bullet always outranks an off-topic one;
    provenance/freshness only decide order among equally relevant facts.
    Max = 0.5 (operator tier) + 0.45 (verified today) = 0.95.
    """
    return round(0.5 * tier_weight(tier) + freshness_bonus(verified_at, today=today), 4)


def infer_tier_from_path(rel_path: Path | str) -> str:
    """Tier implied by where a note lives when frontmatter doesn't say."""
    parts = [p.lower() for p in Path(rel_path).parts]
    if "_operator_facts" in parts:
        return TIER_OPERATOR
    if parts and parts[-1].startswith("_sources"):
        return TIER_LINK
    return TIER_VAULT


def note_metadata(
    meta: dict[str, str],
    rel_path: Path | str,
) -> tuple[str, date | None, date | None, str]:
    """(tier, verified_at, expires, source_url) from note frontmatter + path.

    ``verified_at:`` falls back to ``date:`` (the operator-facts writer has
    always stamped ``date:``); ``source:`` counts only when it's a URL.
    """
    declared = (meta.get("tier") or "").strip().lower()
    tier = declared if declared in TIER_WEIGHTS else infer_tier_from_path(rel_path)
    verified_at = parse_iso_date(meta.get("verified_at")) or parse_iso_date(meta.get("date"))
    expires = parse_iso_date(meta.get("expires"))
    # `source:` is canonical — both writers emit it (core/source_capture.py,
    # core/operator_facts.py). `source_url:` is accepted because the shipped
    # docs/vault_templates/_sources.md briefly told operators to use that key, and a
    # hand-written note must not lose its provenance over the spelling.
    source = ((meta.get("source") or "") or (meta.get("source_url") or "")).strip()
    source_url = source if source.lower().startswith(("http://", "https://")) else ""
    return tier, verified_at, expires, source_url
