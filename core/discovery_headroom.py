"""#590: show remaining rate-limit headroom *before* the discovery pool starts.

Every number here already existed; none of it was visible until something hit a
wall. `has_quota_for_search()` refuses a call, the Apify breaker trips, or the
operator runs `ops reliability` afterwards and reads what was already spent. A
discovery pool of eight signals is exactly the moment the remaining budget is
still a decision.

Read-only and fail-open: this never writes a store and never raises into
`build_registry`. An unreadable store reports **unknown**, not zero -- a fresh
machine with no quota file has full quota, and printing "0 units" there would be
the same defect as reporting an unreachable source as clean.
"""

from __future__ import annotations

import threading

from core.logging import get_logger

logger = get_logger("core.discovery_headroom")

_emit_lock = threading.Lock()
_last_line: str | None = None

# Cheapest real search call, so "can this pool finish" is a floor not a guess.
_UNITS_PER_SIGNAL_SEARCH = 100


def _youtube_units() -> tuple[int | None, int | None]:
    """(remaining units, uploads remaining). None means unreadable, not zero."""
    try:
        from apis.youtube_quota import get_usage_summary, uploads_remaining

        summary = get_usage_summary() or {}
        limit = summary.get("units_limit")
        used = summary.get("units_used")
        if limit is None or used is None:
            return None, None
        remaining = max(0, int(limit) - int(used))
        return remaining, int(uploads_remaining(summary))
    except Exception as exc:
        logger.debug("youtube headroom unreadable: %s", exc)
        return None, None


def _llm_spend_today() -> float | None:
    try:
        from core.quota_governor import llm_spend_today

        return float(llm_spend_today())
    except Exception as exc:
        logger.debug("llm spend unreadable: %s", exc)
        return None


def _apify_note() -> str:
    """Per-purpose Apify usage, only for purposes that have a recorded reading."""
    try:
        from core.quota_governor import apify_get_usage, apify_is_exhausted

        parts: list[str] = []
        for purpose in ("tiktok_trends", "youtube_competitors"):
            exhausted, why = apify_is_exhausted(purpose)
            if exhausted:
                parts.append(f"{purpose} EXHAUSTED ({why[:40]})")
                continue
            usage = apify_get_usage(purpose)
            if isinstance(usage, dict) and usage.get("limit"):
                parts.append(f"{purpose} {usage.get('usage', 0):.2f}/{usage['limit']:.2f}")
        return "; ".join(parts)
    except Exception as exc:
        logger.debug("apify headroom unreadable: %s", exc)
        return ""


def headroom_line(*, signal_count: int) -> str:
    """One line for the operator, immediately before the pool spends anything."""
    units, uploads = _youtube_units()
    bits: list[str] = [f"{signal_count} signal(s) about to run"]

    if units is None:
        bits.append("YouTube quota unknown (no reading)")
        short = False
    else:
        bits.append(f"{units} YouTube units left")
        bits.append(f"{uploads if uploads is not None else '?'} upload(s) left")
        short = units < signal_count * _UNITS_PER_SIGNAL_SEARCH

    spend = _llm_spend_today()
    if spend is not None:
        bits.append(f"LLM ${spend:.4f} today")

    apify = _apify_note()
    if apify:
        bits.append(apify)

    line = "Headroom: " + " | ".join(bits)
    if short:
        line = (
            f"! {line} -- not enough units for every signal to search; "
            "the pool will run degraded"
        )
    return line


def emit_headroom(line: str) -> None:
    """Separate from building the line so the caller can be traced, and so a
    console that cannot encode the text never breaks discovery.

    #723: `build_registry` runs once per variant (`core/pipeline._score_variant`),
    so an unchanged line prints once per process. A number that moved prints again.
    """
    global _last_line
    with _emit_lock:
        if line == _last_line:
            logger.debug("headroom unchanged since last print")
            return
        _last_line = line
    try:
        print(f"  {line}")
    except Exception as exc:  # pragma: no cover - cp1252 consoles
        logger.debug("headroom line not printed: %s", exc)
