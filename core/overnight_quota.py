"""Overnight quota-aware count (candidate 45).

Skip or shrink --count when YouTube remaining < one upload or the Apify
breaker is in. Opt-in (OVERNIGHT_QUOTA_GATE empty/0/off = disabled) so the
suite cannot read the operator's real youtube_quota.json and shrink drafts.
"""

from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger

logger = get_logger("core.overnight_quota")


def gate_enabled() -> bool:
    raw = os.getenv("OVERNIGHT_QUOTA_GATE", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def adjust_count(requested: int) -> tuple[int, str]:
    """Return (count, reason). Fail-open: store errors leave count unchanged."""
    n = max(0, int(requested))
    if not gate_enabled():
        return n, ""
    reason_parts: list[str] = []

    try:
        from apis.apify_client import apify_disabled
        from core.quota_governor import apify_is_exhausted

        if apify_disabled():
            n = min(n, 1)
            reason_parts.append("Apify session breaker in — shrinking overnight count")
        else:
            exhausted, why = apify_is_exhausted("main")
            if exhausted:
                n = min(n, 1)
                reason_parts.append(
                    f"Apify persisted exhausted ({why or 'credits'}) — shrinking overnight count"
                )
    except Exception as exc:
        logger.debug("overnight apify quota skipped: %s", exc)

    try:
        from apis.youtube_quota import UNITS_VIDEO_INSERT, get_usage_summary

        remaining = int(get_usage_summary().get("remaining") or 0)
        reserve = UNITS_VIDEO_INSERT
        if remaining < reserve:
            n = 0
            reason_parts.append(
                f"YouTube remaining {remaining} < {reserve} upload reserve — skip overnight"
            )
        elif n:
            # Each draft still spends search units (~100-200). Leave the upload reserve.
            headroom = remaining - reserve
            max_topics = max(0, headroom // 200)
            if max_topics < n:
                n = max_topics
                reason_parts.append(f"YouTube headroom {headroom} units — overnight count now {n}")
    except Exception as exc:
        logger.debug("overnight youtube quota skipped: %s", exc)

    return max(0, n), "; ".join(reason_parts)


def snapshot() -> dict[str, Any]:
    n, reason = adjust_count(3)
    return {"enabled": gate_enabled(), "example_count": n, "reason": reason}
