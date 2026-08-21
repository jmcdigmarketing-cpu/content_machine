"""Thin-facts abort — stop before the $0.31 TTS line when the draft is too thin.

Drafts stay free (script + ledger already saved). Env-gated; the default bar
matches the existing thin-facts warning (3 verified lines) plus a 50% claim-
support floor when the verifier actually ran. Missing verifier data fail-opens
so a well-grounded run is never blocked by a skipped extract-tier call.
"""

from __future__ import annotations

import os
from typing import Any


def abort_enabled() -> bool:
    return os.getenv("THIN_FACTS_TTS_ABORT", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def min_fact_lines() -> int:
    try:
        return max(0, int(os.getenv("THIN_FACTS_MIN_LINES", "3")))
    except (TypeError, ValueError):
        return 3


def min_claim_support() -> float:
    try:
        val = float(os.getenv("THIN_FACTS_MIN_SUPPORT", "0.5"))
        return val if 0.0 <= val <= 1.0 else 0.5
    except (TypeError, ValueError):
        return 0.5


def thin_facts_abort_reason(
    *,
    fact_count: int,
    features: dict[str, Any] | None = None,
) -> str | None:
    """Why TTS should be skipped, or None when the draft is grounded enough."""
    if not abort_enabled():
        return None
    if fact_count < min_fact_lines():
        return (
            f"thin facts: {fact_count} verified line(s) "
            f"(min {min_fact_lines()}) — aborting before TTS"
        )
    rate = None
    if features:
        rate = features.get("claim_support_rate")
        if rate is None:
            ver = features.get("claim_verification") or {}
            if isinstance(ver, dict):
                rate = ver.get("support_rate")
    if rate is None:
        return None  # verifier didn't run — fail-open on the support bar
    try:
        support = float(rate)
    except (TypeError, ValueError):
        return None
    floor = min_claim_support()
    if support < floor:
        return f"thin facts: claim support {support:.0%} below {floor:.0%} " "— aborting before TTS"
    return None
