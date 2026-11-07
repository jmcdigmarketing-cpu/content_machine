"""The bridge's lane numbers (decision 82), each with the run of weeks its "done" asks for - wave 155.

Every lane of `bridge_plan.md` ends on one number. The hours lane's is `ypp_readiness.hours_lane`
(#1746); these are the rest, printed under it in the bridge scoreboard (`ops ypp`, the weekly
report):

- #1621 (B01 ideas, views): the median Short's first-week organic views, by the week it went
  public, against the 30-day median - done when it rises four weeks running.
- #1646 (B02 the first seconds, views): the week's median stayed share against 45% - four weeks
  above.
- #1671 (B03 cadence, views): organic views a day, the last 7 days' average, against ~250 (10-27).
- #1696 (B04 formats, views): the best format of 90 days (by median first-week views, three Shorts
  or more) and its share of each week's uploads - rising.
- #1721 (B05 subscribers): the sync's 7-day net subscribers, kept a week at a time
  (`subs_weeks`), against +1.0 a week - done at +10 four weeks running. Ads are off since 10-27, so
  the net is organic.
- #1771 (B07 money): dollars earned outside YouTube this month (the money ledger) against $0.

A week is its ISO week; a Short whose first week is not measured yet is not in it.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.success.lanes")

LANE_WEEKS = 4
STAYED_BAR = 0.45
DAILY_BASE = 250  # organic views a day on 10-27
SUBS_BASE = 1.0  # organic subscribers a week on 10-27
SUBS_BAR = 10


def rising_run(series: list[float]) -> int:
    """How many rises in a row end the series."""
    run = 0
    for before, after in zip(series[-2::-1], series[::-1], strict=False):  # one shorter
        if after > before:
            run += 1
        else:
            break
    return run


def above_run(series: list[float], bar: float) -> int:
    """How many values in a row at the end are over `bar`."""
    run = 0
    for value in reversed(series):
        if value > bar:
            run += 1
        else:
            break
    return run


def _week(when: datetime) -> str:
    year, week, _ = when.isocalendar()
    return f"{year}-W{week:02d}"


def _by_week(shorts: list[dict[str, Any]], key: str) -> list[tuple[str, float]]:
    groups: dict[str, list[float]] = {}
    for short in shorts:
        value = short.get(key)
        if isinstance(value, (int, float)):
            groups.setdefault(_week(short["when"]), []).append(float(value))
    return [(week, statistics.median(values)) for week, values in sorted(groups.items())]


def _run_text(run: int, *, word: str) -> str:
    return (
        f"done - {run} weeks running"
        if run >= LANE_WEEKS
        else f"{word} {run} of {LANE_WEEKS} weeks"
    )


def views_lane(shorts: list[dict[str, Any]], *, today: date) -> str:
    """#1621: the latest week's median Short against the 30-day median."""
    weeks = _by_week(shorts, "views7")
    if not weeks:
        return "Views lane (B01, #1621): no Short's first week measured yet"
    since = datetime.combine(today - timedelta(days=30), datetime.min.time(), tzinfo=timezone.utc)
    month = [s["views7"] for s in shorts if s["when"] >= since]
    base = f", against {statistics.median(month):,.0f} over 30 days" if month else ""
    run = rising_run([m for _w, m in weeks])
    return (f"Views lane (B01, #1621): the median Short's first week, {weeks[-1][1]:,.0f} organic "
            f"views ({weeks[-1][0]}){base} - {_run_text(run, word='rising')}")  # fmt: skip


def stayed_lane(shorts: list[dict[str, Any]]) -> str:
    """#1646: the latest week's median stayed share against 45%."""
    weeks = _by_week(shorts, "stayed")
    if not weeks:
        return "Stayed lane (B02, #1646): no stayed share measured yet"
    run = above_run([m for _w, m in weeks], STAYED_BAR)
    tail = (f"done - {run} weeks running above {STAYED_BAR:.0%}" if run >= LANE_WEEKS
            else f"{run} of {LANE_WEEKS} weeks above {STAYED_BAR:.0%}")  # fmt: skip
    return (f"Stayed lane (B02, #1646): the week's median stayed share {weeks[-1][1]:.0%} "
            f"({weeks[-1][0]}) - {tail}")  # fmt: skip


def daily_lane(rows: list[Any], *, today: date) -> str:
    """#1671: the channel's organic views a day over the last 7 days, against ~250 on 10-27."""
    import json

    from analytics.promotions import _organic_by_day, _per_day

    series = []
    for row in rows or []:
        try:
            metrics = json.loads(getattr(row, "metrics_json", "") or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(metrics, dict):
            series.append(_organic_by_day(metrics))
    a_day = _per_day(series, today - timedelta(days=7), today - timedelta(days=1))
    if a_day is None:
        return "Cadence lane (B03, #1671): no views a day measured in the last 7 days"
    return (f"Cadence lane (B03, #1671): {a_day:,.0f} organic views a day (the last 7 days) "
            f"against ~{DAILY_BASE} on 10-27")  # fmt: skip


def format_lane(shorts: list[dict[str, Any]]) -> str:
    """#1696: the best format and its share of each week's uploads."""
    groups: dict[str, list[int]] = {}
    for short in shorts:
        groups.setdefault(str(short.get("format") or ""), []).append(int(short["views7"]))
    ranked = sorted(((statistics.median(v), name) for name, v in groups.items() if len(v) >= 3),
                    reverse=True)  # fmt: skip
    if not ranked:
        return "Format lane (B04, #1696): no format has three Shorts measured yet"
    median, best = ranked[0]
    weeks: dict[str, list[str]] = {}
    for short in shorts:
        weeks.setdefault(_week(short["when"]), []).append(str(short.get("format") or ""))
    shares = [sum(1 for f in fmts if f == best) / len(fmts) for _w, fmts in sorted(weeks.items())]
    run = rising_run(shares)
    return (f"Format lane (B04, #1696): the best format, {best} (median {median:,.0f} first-week "
            f"organic views), was {shares[-1]:.0%} of the latest week's uploads - its share "
            f"{_run_text(run, word='rising')}")  # fmt: skip


def _week_days(key: str) -> tuple[date, date] | None:
    """The Monday and Sunday of an ISO week key ("2026-W44")."""
    try:
        year, week = key.split("-W")
        monday = date.fromisocalendar(int(year), int(week), 1)
    except (ValueError, AttributeError):
        return None
    return monday, monday + timedelta(days=6)


def organic_weeks(weeks: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, float]:
    """#1830 (wave 158): each week's net subscribers less what the ledger's campaigns brought in it
    - W44's +29 from the Oct 26-27 campaigns was counted as the channel's own."""
    from core.success.bridge import campaign_subscribers

    out: dict[str, float] = {}
    for key in sorted(weeks):
        days = _week_days(key)
        paid = campaign_subscribers(entries, days[0], days[1]) if days else 0.0
        out[key] = float(weeks[key]) - paid
    return out


def subscribers_lane(
    numbers: dict[str, Any],
    *,
    entries: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> str:
    """#1721: the last 7 days' net subscribers and the weeks in a row at +10 - #1830: organic, less
    what the ledger's ad campaigns brought in each window."""
    gained, lost = numbers.get("subs_gained_7d"), numbers.get("subs_lost_7d")
    if not isinstance(gained, (int, float)) or not isinstance(lost, (int, float)):
        return ""
    from core.success.bridge import campaign_subscribers

    day = today or date.today()
    net = int(gained) - int(lost)
    paid = campaign_subscribers(entries or [], day - timedelta(days=6), day)
    organic = round(net - paid)
    weeks = organic_weeks(numbers.get("subs_weeks") or {}, entries or [])
    run = above_run([weeks[k] for k in sorted(weeks)], SUBS_BAR - 0.5)
    tail = (f"done - {run} weeks running at +{SUBS_BAR}" if run >= LANE_WEEKS
            else f"{run} of {LANE_WEEKS} weeks at +{SUBS_BAR}")  # fmt: skip
    note = f" organic ({net:+d} with the campaigns' {paid:g})" if paid else ""
    return (f"Subscribers lane (B05, #1721): {organic:+d} subscribers in the last 7 days{note} (ads "
            f"off since 10-27) against +{SUBS_BASE:.1f} a week on 10-27 - {tail}")  # fmt: skip


def money_lane(income: list[dict[str, Any]], *, today: date) -> str:
    """#1771: dollars earned outside YouTube this month, against $0."""
    month = f"{today:%Y-%m}"
    earned = sum(float(r.get("amount") or 0) for r in income or []
                 if str(r.get("date") or "")[:7] == month)  # fmt: skip
    return (f"Money lane (B07, #1771): ${earned:,.2f} earned outside YouTube this month, "
            f"against $0")  # fmt: skip


def lane_lines(
    channel_id: str,
    *,
    today: date | None = None,
    numbers: dict[str, Any] | None = None,
    stores: bool = True,
    rows: list[Any] | None = None,
    features: Callable[[int], dict[str, Any]] | None = None,
    income: list[dict[str, Any]] | None = None,
    entries: list[dict[str, Any]] | None = None,
) -> list[str]:
    """The lane numbers, one line each. With `stores` false only what `numbers` carries.
    `entries` is the spend ledger (#1830: the campaigns' subscribers leave the subscriber lane)."""
    day = today or date.today()
    out: list[str] = []
    try:
        if stores:
            from core.success.formats import measured_shorts

            if rows is None:
                from storage.repositories.publish_log import get_publish_log_repository, is_seeded

                rows = [r for r in get_publish_log_repository().list_uploaded_for_channel(channel_id)
                        or [] if not is_seeded(r)]  # fmt: skip
            shorts = measured_shorts(channel_id, today=day, rows=rows, features=features)
            out += [views_lane(shorts, today=day), stayed_lane(shorts), daily_lane(rows, today=day),
                    format_lane(shorts)]  # fmt: skip
        if entries is None and stores:
            from core.money.ledger import entries as ledger_entries

            entries = list(ledger_entries())
        subs = subscribers_lane(numbers or {}, entries=entries or [], today=day)
        if subs:
            out.append(subs)
        if stores:
            if income is None:
                from core.money.ledger import income_rows

                income = income_rows()
            out.append(money_lane(income, today=day))
    except Exception as exc:
        logger.debug("lane numbers skipped: %s", exc)
    return out
