"""The month's test (#2031, decision 113): each number against where it started.

The operator, 2026-11-13: "Either rapid rapid improvement or the plug is pulled, 1 month until the
potential end." `config/decision_test.json` holds the window per channel. The start line is taken
once - at the first metrics sync on or after the window's first day - from the numbers the sync
already stores (`core/ypp_readiness.load_ypp_numbers`): organic Shorts views in 28 days, organic
subscribers (`bridge.organic_subscribers`: YouTube's count less the ad campaigns') and long-form
hours. `decision_line` prints today's against it, for `ops status` and the weekly report. It
reports; the decision is the operator's.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.success.decision")

_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "decision_test.json",
)
BASELINE_TEMPLATE = os.path.join(DATA_DIR, "decision_test_{channel}.json")
_KEYS = ("shorts_views_28d", "organic_subscribers", "long_hours_365d")


def window(channel_id: str) -> tuple[date, date] | None:
    """(first day, decision day) for the channel, or None when it has no test."""
    try:
        with open(_CONFIG, encoding="utf-8") as handle:
            row = (json.load(handle) or {}).get(channel_id) or {}
        return date.fromisoformat(str(row["start"])[:10]), date.fromisoformat(str(row["end"])[:10])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        logger.debug("decision test unread for %s: %s", channel_id, exc)
        return None


def _path(channel_id: str) -> str:
    return BASELINE_TEMPLATE.format(channel=channel_id)


def _entries() -> list[dict[str, Any]]:
    try:
        from core.money.ledger import entries

        return list(entries())
    except Exception as exc:
        logger.debug("spend ledger unread: %s", exc)
        return []


def snapshot(
    numbers: dict[str, Any], entries: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """The three numbers as they stand - None for one the sync has not measured."""
    from core.success.bridge import organic_subscribers

    rows = _entries() if entries is None else list(entries)
    nums = dict(numbers or {})
    return {
        "shorts_views_28d": nums.get("shorts_views_28d"),
        "organic_subscribers": organic_subscribers(nums.get("subscribers"), rows)["count"],
        "long_hours_365d": nums.get("long_hours_365d"),
    }


def load_baseline(channel_id: str, *, path: str | None = None) -> dict[str, Any]:
    try:
        with open(path or _path(channel_id), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def capture_baseline(
    channel_id: str,
    numbers: dict[str, Any],
    *,
    today: date | None = None,
    entries: list[dict[str, Any]] | None = None,
    path: str | None = None,
) -> bool:
    """Keep the start line - once, inside the window, when the sync has numbers. True when
    written."""
    span = window(channel_id)
    day = today or date.today()
    if span is None or not span[0] <= day <= span[1] or not numbers:
        return False
    target = path or _path(channel_id)
    if load_baseline(channel_id, path=target):
        return False
    shot = snapshot(numbers, entries)
    if all(shot[key] is None for key in _KEYS):
        return False
    data = {"channel_id": channel_id, "day": day.isoformat(), **shot}
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    tmp = f"{target}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp, target)
    return True


def _whole(value: float) -> str:
    return f"{value:,.0f}"


def _part(label: str, now: Any, was: Any, *, hours: bool = False, percent: bool = False) -> str:
    if now is None:
        return f"{label} not measured"
    shown = f"{float(now):,.1f}" if hours else _whole(float(now))
    if was is None:
        return f"{label} {shown} (no start line)"
    start = f"{float(was):,.1f}" if hours else _whole(float(was))
    delta = float(now) - float(was)
    if percent:
        change = f"{delta / float(was):+.0%}" if float(was) else f"{delta:+,.0f}"
        return f"{label} {shown} ({start} at the start, {change})"
    change = f"{delta:+.1f}" if hours else f"{delta:+,.0f}"
    return f"{label} {shown} ({start}, {change})"


def decision_line(
    channel_id: str,
    *,
    today: date | None = None,
    numbers: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
    entries: list[dict[str, Any]] | None = None,
) -> str:
    """One line: the days left and each number against its start. "" for a channel with no
    test."""
    span = window(channel_id)
    if span is None:
        return ""
    day = today or date.today()
    end = span[1]
    left = (end - day).days
    name = f"{end:%a %b} {end.day}"
    if left >= 0:
        head = f"Decision day {name} ({left} day{'s' if left != 1 else ''} left)"
    else:
        head = f"Decision day was {name}"
    base = load_baseline(channel_id) if baseline is None else dict(baseline)
    if not base:
        return f"{head}: the start line is taken at the next metrics sync"
    if numbers is None:
        from core.ypp_readiness import load_ypp_numbers

        numbers = dict(load_ypp_numbers(channel_id) or {})
    now = snapshot(numbers, entries)
    parts = [
        _part("organic Shorts views in 28 days", now["shorts_views_28d"],
              base.get("shorts_views_28d"), percent=True),
        _part("organic subscribers", now["organic_subscribers"], base.get("organic_subscribers")),
        _part("long-form hours", now["long_hours_365d"], base.get("long_hours_365d"), hours=True),
    ]  # fmt: skip
    return f"{head}: " + "; ".join(parts)
