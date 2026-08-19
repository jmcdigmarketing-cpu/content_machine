"""Reliability time series (O12) — the trend behind the dashboard's snapshot.

`ops reliability` answers "how are things right now". It cannot answer "is this getting
worse", which is the question that actually catches slow degradation: LLM spend creeping
up, YouTube units drifting toward the cap, feeds dying one at a time, a signal that has
been disabled for a week. Every failure this session started as a gradual change nobody
could see, because nothing kept yesterday's numbers.

One row per day, upserted, capped at `RELIABILITY_HISTORY_DAYS` (default 90). Recording
happens from `ops reliability` and `daily-sync`, so simply looking at the dashboard
builds the series — there is no separate job to forget to run.

Read-only and fail-open everywhere: history is diagnostics, and a corrupt or missing
file must never affect a run.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from core.logging import get_logger

logger = get_logger("core.reliability_history")

_MAX_DAYS_DEFAULT = 90


def _max_days() -> int:
    try:
        return max(7, min(int(os.getenv("RELIABILITY_HISTORY_DAYS", str(_MAX_DAYS_DEFAULT))), 365))
    except ValueError:
        return _MAX_DAYS_DEFAULT


def _path() -> str:
    from config.paths import RELIABILITY_HISTORY_FILE, ensure_data_dir

    ensure_data_dir()
    return RELIABILITY_HISTORY_FILE


def _load() -> list[dict[str, Any]]:
    try:
        path = _path()
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            rows = json.load(fh)
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    except Exception as exc:
        logger.debug("reliability history unreadable: %s", exc)
        return []


def _save(rows: list[dict[str, Any]]) -> None:
    try:
        with open(_path(), "w", encoding="utf-8") as fh:
            json.dump(rows[-_max_days() :], fh, indent=2)
    except Exception as exc:
        logger.debug("could not write reliability history: %s", exc)


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    """Reduce a `reliability.gather()` snapshot to the few numbers worth trending."""
    llm = data.get("llm") or {}
    youtube = data.get("youtube") or {}
    cache = data.get("cache") or {}
    signals = data.get("signals") or {}
    apify = data.get("apify") or {}

    feeds_ok = feeds_dead = 0
    try:
        from core.feed_health import STATUS_DEAD, STATUS_OK, load_results
        from core.feed_health import summarize as feed_summary

        counts = feed_summary((load_results() or {}).get("results") or [])
        feeds_ok, feeds_dead = counts.get(STATUS_OK, 0), counts.get(STATUS_DEAD, 0)
    except Exception as exc:
        logger.debug("STATUS_DEAD skipped: %s", exc)

    return {
        "date": date.today().isoformat(),
        "llm_spend_usd": round(float(llm.get("spend_today") or 0.0), 4),
        "llm_dead_models": len(llm.get("dead_models") or {}),
        "youtube_units": int(youtube.get("used") or 0),
        "youtube_limit": int(youtube.get("limit") or 0),
        "apify_exhausted": bool(apify.get("exhausted")),
        "signals_disabled": len(signals.get("disabled") or [])
        + len(signals.get("persisted") or {}),
        "cache_hit_rate": round(float(cache.get("hit_rate") or 0.0), 3),
        "feeds_ok": feeds_ok,
        "feeds_dead": feeds_dead,
    }


def record(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Upsert today's row. Returns the row (empty dict on failure)."""
    try:
        if data is None:
            from core.reliability import gather

            data = gather()
        row = summarize(data)
        rows = [r for r in _load() if r.get("date") != row["date"]]
        rows.append(row)
        rows.sort(key=lambda r: str(r.get("date")))
        _save(rows)
        return row
    except Exception as exc:
        logger.debug("could not record reliability history: %s", exc)
        return {}


def history(days: int = 14) -> list[dict[str, Any]]:
    rows = _load()
    return rows[-max(1, days) :]


def _spark(values: list[float]) -> str:
    """Tiny ASCII trend. ASCII on purpose — the Windows console is cp1252."""
    nums = [v for v in values if isinstance(v, int | float)]
    if not nums:
        return ""
    lo, hi = min(nums), max(nums)
    if hi <= lo:
        return "-" * len(nums)
    ramp = ".:-=+*#"
    return "".join(
        ramp[min(int((v - lo) / (hi - lo) * (len(ramp) - 1)), len(ramp) - 1)] for v in nums
    )


def render(days: int = 14) -> str:
    rows = history(days)
    if not rows:
        return (
            "\nReliability trend\n"
            + "=" * 72
            + "\n  No history yet — run `ops reliability` daily to build it.\n"
        )

    lines = ["", f"Reliability trend (last {len(rows)} day(s))", "=" * 72]
    series = [
        ("LLM spend $", [r.get("llm_spend_usd", 0) for r in rows], "{:.4f}"),
        ("YouTube units", [r.get("youtube_units", 0) for r in rows], "{:.0f}"),
        ("Signals off", [r.get("signals_disabled", 0) for r in rows], "{:.0f}"),
        ("Feeds dead", [r.get("feeds_dead", 0) for r in rows], "{:.0f}"),
        ("Cache hit", [r.get("cache_hit_rate", 0) for r in rows], "{:.2f}"),
    ]
    for label, values, fmt in series:
        latest = values[-1] if values else 0
        first = values[0] if values else 0
        delta = latest - first
        arrow = "flat" if abs(delta) < 1e-9 else ("up" if delta > 0 else "down")
        lines.append(
            f"  {label:14} {_spark(values):16} now={fmt.format(latest):>9}  ({arrow} vs {len(rows)}d ago)"
        )
    lines.append(f"  {'':14} {rows[0].get('date', '')} -> {rows[-1].get('date', '')}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    print(render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
