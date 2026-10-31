"""The bridge's scoreboard (decision 82; wave 134): where the channel stands against the bar.

- `bar_on(day)` - the YPP bar in force that day, from `config/ypp.json` (#1823); the 2027 bar
  rests on third-party reports and says so.
- `organic_subscribers` - YouTube's count less the ad campaigns' (#1697): Google does not count
  ad subscribers toward YPP. "At most" while a campaign has no count, or its count is not final
  (decision 86 - 134 became 195 in a day with both campaigns "ended").
- `race_clock` - the days to the new bar and what each path needs a day (#1825).
- `scoreboard_lines` / `status_line` - the four numbers with their pace (#1822), for `ops ypp`, the
  weekly report and `ops status`. An absent number reads "not measured", never 0.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from core.logging import get_logger

logger = get_logger("core.success.bridge")

_BARS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "ypp.json",
)
# Today's bar when config/ypp.json cannot be read - core/ypp_readiness's constants.
_FALLBACK = {"from": "2023-06-13", "subscribers": 1000, "hours": 4000, "shorts": 10_000_000,
             "source": "YouTube Help"}  # fmt: skip
NEW_BAR_DAY = date(2027, 2, 1)
_UNREACHABLE = 100  # a need over 100x the pace is said plainly
SHORTS_DAYS, HOURS_DAYS, PACE_DAYS = 90, 365, 28


def _day(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def bars() -> list[dict[str, Any]]:
    """The bars by date, oldest first."""
    try:
        with open(_BARS_FILE, encoding="utf-8") as handle:
            rows = (json.load(handle) or {}).get("bars") or []
    except (OSError, ValueError, AttributeError) as exc:
        logger.debug("ypp.json unread: %s", exc)
        rows = []
    good = [r for r in rows if isinstance(r, dict) and r.get("from")]
    return sorted(good, key=lambda r: str(r["from"])) or [dict(_FALLBACK)]


def bar_on(day: str | date) -> dict[str, Any]:
    """#1823: the bar in force on `day`."""
    when = _day(day)
    found = [r for r in bars() if _day(r["from"]) <= when]
    return found[-1] if found else bars()[0]


def next_bar(day: str | date) -> dict[str, Any] | None:
    when = _day(day)
    return next((r for r in bars() if _day(r["from"]) > when), None)


def _bar_text(bar: dict[str, Any]) -> str:
    return (
        f"{int(bar['subscribers']):,} subscribers and {int(bar['hours']):,} long-form hours "
        f"(12 months) or {int(bar['shorts']):,} Shorts views (90 days)"
    )


def bar_lines(today: date | None = None) -> list[str]:
    """Today's bar with its source, then the next one with its date and source."""
    day = today or date.today()
    now = bar_on(day)
    lines = [f"Today's bar: {_bar_text(now)} - {now.get('source')}, since {now['from']}."]
    upcoming = next_bar(day)
    if upcoming:
        lines.append(f"From {upcoming['from']}: {_bar_text(upcoming)} - {upcoming.get('source')}.")
    return lines


def organic_subscribers(total: int | None, entries: list[dict[str, Any]]) -> dict[str, Any]:
    """#1697: {"count", "campaigns", "at_most"} - YouTube's count less every ad campaign's
    subscribers; `at_most` while a campaign has no count or its count is not marked final."""
    ads = [e for e in entries or [] if e.get("kind") == "ads"]
    campaigns = sum(int((e.get("result") or {}).get("subscribers") or 0) for e in ads)
    open_count = any(
        (e.get("result") or {}).get("subscribers") is None
        or not (e.get("result") or {}).get("final")
        for e in ads
    )
    count = None if total is None else max(0, int(total) - campaigns)
    return {"count": count, "campaigns": campaigns, "at_most": open_count, "total": total}


def organic_line(total: int | None, entries: list[dict[str, Any]]) -> str:
    found = organic_subscribers(total, entries)
    if found["count"] is None:
        return "organic subscribers: not measured"
    if found["at_most"]:
        return (
            f"organic subscribers at most {found['count']:,} (YouTube {int(total or 0):,}, "
            f"campaigns {found['campaigns']:,} entered; a campaign's count is not final - "
            "py -m scripts.ops spend result --entry N --subs N --final)"
        )
    return (
        f"organic subscribers {found['count']:,} (YouTube {int(total or 0):,}, campaigns "
        f"{found['campaigns']:,})"
    )


def _need(target: float, have: float, days: int) -> float:
    return max(0.0, (float(target) - float(have)) / days)


def race_clock(numbers: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """#1825: the days to the new bar, and per path what it needs a day under today's bar and
    the new one against the last 28 days' pace (Shorts) or the year's average (hours)."""
    day = today or date.today()
    now, new = bar_on(day), bar_on(NEW_BAR_DAY)
    days_left = max(0, (NEW_BAR_DAY - day).days)
    out: dict[str, Any] = {"days_left": days_left, "lines": []}
    shorts, recent = numbers.get("shorts_views_90d"), numbers.get("shorts_views_28d")
    if shorts is not None:
        pace = round(float(recent) / PACE_DAYS) if recent is not None else None
        out["shorts"] = {
            "need_now": round(_need(now["shorts"], shorts, SHORTS_DAYS)),
            "need_new": round(_need(new["shorts"], shorts, SHORTS_DAYS)),
            "pace": pace,
        }
    hours = numbers.get("long_hours_365d")
    if hours is not None:
        out["hours"] = {
            "need_now": round(_need(now["hours"], hours, HOURS_DAYS), 1),
            "need_new": round(_need(new["hours"], hours, HOURS_DAYS), 1),
            "pace": round(float(hours) / HOURS_DAYS, 2),
        }
    lines = [f"Race clock: {days_left} days to {NEW_BAR_DAY.isoformat()} (the new bar)."]
    for key, label, unit in (("shorts", "Shorts", "views"), ("hours", "Long-form", "hours")):
        path = out.get(key)
        if not path:
            lines.append(f"  {label}: not measured")
            continue
        pace = path["pace"]
        line = (
            f"  {label}: {path['need_now']:,} {unit} a day under today's bar, "
            f"{path['need_new']:,} under the new one; the pace is "
            + (f"{pace:,} a day" if pace is not None else "not measured")
        )
        if pace is not None and path["need_now"] > _UNREACHABLE * max(pace, 0.01):
            line += " - not reachable at this pace"
        lines.append(line)
    out["lines"] = lines
    return out


def _days_to(target: float, have: float, per_day: float | None) -> str:
    if per_day is None or per_day <= 0:
        return "no pace yet"
    days = (float(target) - float(have)) / per_day
    return "reached" if days <= 0 else f"about {days:,.0f} days at that pace"


def _entries() -> list[dict[str, Any]]:
    try:
        from core.money.ledger import entries

        return list(entries())
    except Exception as exc:
        logger.debug("spend ledger unread: %s", exc)
        return []


def _numbers(channel_id: str) -> dict[str, Any]:
    try:
        from core.ypp_readiness import load_ypp_numbers

        return dict(load_ypp_numbers(channel_id) or {})
    except Exception as exc:
        logger.debug("ypp numbers unread: %s", exc)
        return {}


def scoreboard_lines(
    channel_id: str,
    *,
    numbers: dict[str, Any] | None = None,
    entries: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> list[str]:
    """#1822 (B10.1): the four numbers, each with its pace and the days to today's bar."""
    nums = _numbers(channel_id) if numbers is None else dict(numbers)
    rows = _entries() if entries is None else list(entries)
    day = today or date.today()
    bar = bar_on(day)
    lines = ["Bridge scoreboard (decision 82) - what counts toward YPP:"]
    subs = organic_line(nums.get("subscribers"), rows)
    net = nums.get("subs_net_28d")
    if nums.get("subscribers") is not None and net is not None:
        subs += f"; {int(net):+,} in 28 days (ads included)"
    lines.append(f"  {subs}")
    engaged = nums.get("shorts_engaged_90d")
    if engaged is None:
        lines.append("  engaged Shorts views (90 days): not measured (the next metrics sync asks)")
    else:
        lines.append(
            f"  engaged Shorts views (90 days): {int(engaged):,} of {int(bar['shorts']):,}"
        )
    hours = nums.get("long_hours_365d")
    if hours is None:
        lines.append("  long-form hours (365 days): not measured")
    else:
        per_day = float(hours) / HOURS_DAYS
        lines.append(
            f"  long-form hours (365 days): {float(hours):,.1f} of {int(bar['hours']):,} - "
            f"{_days_to(bar['hours'], hours, per_day)}"
        )
    lines.append("  money outside YouTube: not tracked yet (wave 136)")
    # #1797 and #1728 (wave 135); the store reads only when the numbers are the stored ones
    from core.success import scorecard

    try:
        costs = scorecard.cost_rows(channel_id, today=day) if numbers is None else []
        minutes = scorecard.long_minutes(channel_id) if numbers is None else []
    except Exception as exc:
        logger.debug("scorecard rows unread: %s", exc)
        costs, minutes = [], []
    lines.append(f"  {scorecard.week_cost_line(costs)}")
    hours_bars = (int(bar["hours"]), int(bar_on(NEW_BAR_DAY)["hours"]))
    lines.extend(f"  {line}" for line in scorecard.hours_lines(
        minutes, have=nums.get("long_hours_365d"), bars=hours_bars))  # fmt: skip
    lines.extend(f"  {line}" for line in race_clock(nums, today=day)["lines"])
    return lines


def status_line(
    channel_id: str,
    *,
    numbers: dict[str, Any] | None = None,
    entries: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> str:
    """`ops status`' one line for the bridge."""
    nums = _numbers(channel_id) if numbers is None else dict(numbers)
    rows = _entries() if entries is None else list(entries)
    found = organic_subscribers(nums.get("subscribers"), rows)
    subs = (
        "organic subscribers not measured"
        if found["count"] is None
        else f"organic subscribers {'at most ' if found['at_most'] else ''}{found['count']:,}"
    )
    engaged = nums.get("shorts_engaged_90d")
    hours = nums.get("long_hours_365d")
    parts = [
        subs,
        f"{int(engaged):,} engaged Shorts views"
        if engaged is not None
        else "engaged Shorts views not measured",
        f"{float(hours):,.1f} long-form hours" if hours is not None else "hours not measured",
        f"{race_clock(nums, today=today)['days_left']} days to the new bar",
    ]
    return "Bridge: " + " · ".join(parts)
