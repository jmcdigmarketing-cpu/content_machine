"""#158 (core slice): one read-only tower over every cost lane.

TTS, Apify, YouTube units and LLM spend each already had a reader, spread across
`ops reliability`, `ops economics`, the #590 headroom line and #378/#722's
free-tier calendar. Nothing put them side by side under one rule, and the rule is
the one #590 set: **an unreadable lane is unknown, never zero**. A fresh machine
with no quota file has full quota; printing "0 used" there reads as "all clear"
for the wrong reason, and printing "0 left" reads as "out".

Read-only and fail-open: never writes a store, never raises. The Qt panel over
`gather_tower()` is the remainder of #158.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timezone

from core.logging import get_logger

logger = get_logger("core.cost_tower")

_NEAR_SHARE = 0.8
_APIFY_PURPOSES = ("tiktok_trends", "youtube_competitors")


@dataclass
class TowerRow:
    lane: str
    item: str
    used: float | None
    limit: float | None
    state: str  # ok | near | over | unknown
    resets: str | None = None
    note: str = ""


def _state(used: float | None, limit: float | None) -> str:
    if used is None:
        return "unknown"
    if not limit or limit <= 0:
        return "ok"
    if used >= limit:
        return "over"
    if used >= limit * _NEAR_SHARE:
        return "near"
    return "ok"


def _env_float(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _reset(provider: str) -> str | None:
    try:
        from core.reset_window import next_reset, reset_window_enabled

        if not reset_window_enabled():
            return None
        nxt = next_reset(provider)
        return nxt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if nxt else None
    except Exception as exc:
        logger.debug("reset time for %s unavailable: %s", provider, exc)
        return None


def _tts_rows() -> list[TowerRow]:
    try:
        from core.reliability import _elevenlabs_section
        from core.unit_economics import _plan_chars, allocated_vs_marginal_oneliner

        section = _elevenlabs_section()
        used = section.get("chars_used")
        limit = section.get("budget") or _plan_chars()
        note = allocated_vs_marginal_oneliner()
    except Exception as exc:
        logger.debug("tts lane unreadable: %s", exc)
        return [TowerRow("TTS", "ElevenLabs chars", None, None, "unknown")]
    used_f = float(used) if isinstance(used, int | float) else None
    return [
        TowerRow(
            "TTS",
            "ElevenLabs chars",
            used_f,
            float(limit),
            _state(used_f, float(limit)),
            None,
            note,
        )
    ]


def _apify_rows() -> list[TowerRow]:
    rows: list[TowerRow] = []
    resets = _reset("apify")
    for purpose in _APIFY_PURPOSES:
        try:
            from core.quota_governor import apify_get_usage, apify_is_exhausted

            exhausted, why = apify_is_exhausted(purpose)
            if exhausted:
                rows.append(TowerRow("Apify", purpose, None, None, "over", resets, why[:60]))
                continue
            usage = apify_get_usage(purpose)
        except Exception as exc:
            logger.debug("apify lane %s unreadable: %s", purpose, exc)
            usage = None
        if isinstance(usage, dict) and usage.get("limit"):
            used = float(usage.get("usage") or 0.0)
            limit = float(usage["limit"])
            rows.append(TowerRow("Apify", purpose, used, limit, _state(used, limit), resets))
        else:
            rows.append(
                TowerRow("Apify", purpose, None, None, "unknown", resets, "no recorded reading")
            )
    return rows


def _youtube_rows() -> list[TowerRow]:
    try:
        from apis.youtube_quota import daily_limit
        from core.discovery_headroom import _youtube_units

        units, uploads = _youtube_units()
        limit = float(daily_limit())
    except Exception as exc:
        logger.debug("youtube lane unreadable: %s", exc)
        units, uploads, limit = None, None, None
    resets = _reset("youtube")
    if units is None or limit is None:
        return [TowerRow("YouTube", "daily units", None, limit, "unknown", resets, "no reading")]
    used = max(0.0, limit - float(units))
    note = f"{uploads if uploads is not None else '?'} upload(s) left"
    return [TowerRow("YouTube", "daily units", used, limit, _state(used, limit), resets, note)]


def _llm_rows() -> list[TowerRow]:
    try:
        from core.discovery_headroom import _llm_spend_today

        spend = _llm_spend_today()
    except Exception as exc:
        logger.debug("llm lane unreadable: %s", exc)
        spend = None
    budget = _env_float("LLM_DAILY_BUDGET_USD")
    note = "" if budget else "no LLM_DAILY_BUDGET_USD set"
    return [TowerRow("LLM", "spend today", spend, budget, _state(spend, budget), None, note)]


def _free_tier_rows() -> list[TowerRow]:
    try:
        from core.free_tier_calendar import expiring_windows

        windows = expiring_windows()
    except Exception as exc:
        logger.debug("free-tier lane unreadable: %s", exc)
        return []
    rows: list[TowerRow] = []
    for window in windows:
        provider = str(window.get("provider"))
        kind = str(window.get("kind") or "")
        if window.get("unknown"):
            rows.append(TowerRow("Free tier", provider, None, None, "unknown", None, kind))
        elif window.get("closed"):
            rows.append(TowerRow("Free tier", provider, None, None, "over", None, f"{kind} closed"))
        else:
            # A recurring reset refills quota; only a window that *ends* turns a $0
            # run into a paid one. Measured: the daily YouTube reset read NEAR daily.
            state = "ok" if window.get("recurring") else "near"
            verb = "resets" if window.get("recurring") else "ends"
            note = f"{kind} {verb} in {window['days']}d"
            rows.append(TowerRow("Free tier", provider, None, None, state, None, note))
    return rows


def gather_tower() -> list[TowerRow]:
    """Every lane, in the order an operator reads a bill: biggest cost first."""
    return _tts_rows() + _apify_rows() + _youtube_rows() + _llm_rows() + _free_tier_rows()


def _fmt(value: float | None) -> str:
    if value is None:
        return "?"
    if value >= 100:
        return f"{value:,.0f}"
    return f"{value:.2f}"


def amount_text(row: TowerRow) -> str:
    """`used / limit`, shared by the ASCII tower and the panel. `is not None`, not
    truthiness: a real 0.00 spend is a reading."""
    if row.used is None and row.limit is None:
        return "-"
    return f"{_fmt(row.used)} / {_fmt(row.limit)}"


def render_tower(rows: list[TowerRow] | None = None) -> str:
    rows = rows if rows is not None else gather_tower()
    lines = ["Cost Control Tower", "=" * 72]
    for row in rows:
        amount = amount_text(row)
        line = f"  {row.lane:<10} {row.item:<22} {amount:<20} {row.state.upper():<8}"
        if row.resets:
            line += f" resets {row.resets}"
        lines.append(line.rstrip())
        if row.note:
            lines.append(f"  {'':<10} {row.note}")
    lines.append("")
    lines.append("Read-only. UNKNOWN means no reading, never zero.")
    return "\n".join(lines)
