"""Per-source trust from recorded corrections (#342, operator's choice: corrections only).

Tiers are set per section (web, signal, vault ...), not per source, and nothing tied a
correction back to where a claim came from. The records that do name a source:

- the post-publish correction dossier's negative facts - `core/correction_dossier` writes
  "source retracted after publish (<url>, video <id>)" as the reason. These are real
  corrections and they move the weight;
- the operator's rejects at the key-facts prompt (`features["vault_relevance"]`). A reject
  usually means "off-topic", not "wrong", so they are shown and never applied.

`source_factor` is 1.0 until a source (its registrable domain) has
`TRUST_MIN_CORRECTIONS` corrections (default 2), then drops 0.05 per correction to a floor
of 0.85. It scales the tier part of a vault fact's confidence and its ranking bonus.
Demotion only: promotion would need a record of a source being right, which nothing keeps.
"""

from __future__ import annotations

import json
import os
from collections import Counter

from core.logging import get_logger

logger = get_logger("core.facts.trust")

_STEP = 0.05
_FLOOR = 0.85


def min_corrections() -> int:
    """`TRUST_MIN_CORRECTIONS` (default 2): one correction is an anecdote."""
    try:
        value = int(os.getenv("TRUST_MIN_CORRECTIONS", "") or 2)
    except ValueError:
        value = 2
    return max(1, value)


def _domain(url: str) -> str:
    from core.source_diversity import registrable_domain

    return registrable_domain(url) if url else ""


def correction_counts() -> dict[str, int]:
    """registrable domain -> corrections recorded against it."""
    from core.negative_facts import all_records
    from core.source_diversity import urls_from_text

    counts: Counter[str] = Counter()
    for row in all_records():
        for url in urls_from_text(str(row.get("reason") or ""))[:1]:
            domain = _domain(url.rstrip(",).;"))
            if domain:
                counts[domain] += 1
    return dict(counts)


def factor_for(corrections: int) -> float:
    if corrections < min_corrections():
        return 1.0
    return round(max(_FLOOR, 1.0 - _STEP * corrections), 2)


def source_factor(source_url: str) -> float:
    """0.85..1.0 weight for a fact from `source_url`; 1.0 when nothing says otherwise."""
    domain = _domain(source_url or "")
    if not domain:
        return 1.0
    try:
        return factor_for(correction_counts().get(domain, 0))
    except Exception as exc:
        logger.debug("source trust unavailable: %s", exc)
        return 1.0


def reject_counts(channel_id: str) -> dict[str, tuple[int, int]]:
    """domain -> (rejected, offered) at the key-facts prompt, from run features."""
    from storage.repositories.content_runs import get_content_run_repository

    rejected: Counter[str] = Counter()
    offered: Counter[str] = Counter()
    for run in get_content_run_repository().list_for_channel(channel_id) or []:
        try:
            features = json.loads(getattr(run, "features_json", None) or "{}")
        except (TypeError, ValueError):
            continue
        rows = features.get("vault_relevance") if isinstance(features, dict) else None
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            domain = _domain(str(row.get("source_url") or ""))
            if not domain:
                continue
            offered[domain] += 1
            if row.get("operator_override") == "rejected":
                rejected[domain] += 1
    return {d: (rejected[d], offered[d]) for d in offered}


def report_lines(channel_id: str) -> list[str]:
    """`ops source-trust`: corrections per source and the weight they give it."""
    corrections = correction_counts()
    lines = [
        f"Source trust (#342) - {channel_id}: corrections lower a source's weight from "
        f"{min_corrections()} on (x{_FLOOR:.2f} floor); key-facts rejects are shown only"
    ]
    if not corrections:
        lines.append("  no corrections recorded (the post-publish correction scan writes them)")
    for domain, count in sorted(corrections.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"  {domain}: {count} correction(s) -> weight x{factor_for(count):.2f}")
    rejects: dict[str, tuple[int, int]] = {}
    try:
        rejects = reject_counts(channel_id)
    except Exception as exc:
        logger.debug("key-facts rejects unavailable: %s", exc)
    shown = [(d, r, n) for d, (r, n) in rejects.items() if r]
    for domain, rejected, offered in sorted(shown, key=lambda t: (-t[1], t[0]))[:10]:
        lines.append(
            f"  {domain}: {rejected} of {offered} rejected at key facts (shown, not applied)"
        )
    return lines
