"""Dated series entries: the GTA 6 launch moments, its long videos and launch week's slots.

`config/series.json` rows by kind (decision 84):
- `moment` - a Short on its `on` date ("GTA 6 pre-load, file size and unlock times"), drafted
  overnight as an extra draft the way the countdown is; `needs` words must appear in the
  subject's headlines that week or it is skipped with the reason; `on: null` waits for a date;
  `publish_at` (#1870) is the time it goes public, once Rockstar states it.
- `long` - a 10-12 minute 16:9 video on its `on` date (#1850), drafted long and rendered only
  after the operator's review.
- `slots` - extra public hours for videos naming the subject between `from` and `to` (#1868),
  and the days a story naming it on five outlets is drafted first (#1867).

`SERIES_DATED=false` stops the moments and long videos (the suite does).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

from core.logging import get_logger
from core.series.countdown import (
    channel_zone,
    feed_headlines,
    headline_facts,
    series_rows,
    subject_headlines,
)

logger = get_logger("core.series.dated")

BASE_HOURS = (12, 22)  # spaced_queue._TWICE_DAILY
JUMP_OUTLETS = 5  # #1867: a launch-week story on five outlets is drafted first
_NEEDS_HOURS = 24 * 7
_FACTS = {"long": (24 * 7, 12), "moment": (48, 6)}  # (hours back, lines) by kind


def dated_enabled() -> bool:
    from core.providers import flag_enabled

    return flag_enabled("SERIES_DATED", default=True)


def channel_day(channel_id: str, now: datetime | None = None) -> date:
    """Today in the channel's timezone."""
    return (now or datetime.now(timezone.utc)).astimezone(channel_zone(channel_id)).date()


def _day(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _names(row: dict[str, Any]) -> list[str]:
    names = row.get("names") or [row.get("subject")]
    return [str(n) for n in names if str(n or "").strip()]


def _active(row: dict[str, Any], day: date) -> bool:
    try:
        return _day(row["from"]) <= day <= _day(row["to"])
    except (KeyError, TypeError, ValueError):
        return False


def slot_hours(channel_id: str, title: str, day: str | date) -> tuple[int, ...]:
    """#1868 (B11.22): the public hours for a video titled `title` on `day` - noon and 10 PM, plus
    a `slots` row's extra hours when the title names its subject inside its dates."""
    from apis.topic_tokens import names_any

    when = _day(day)
    hours = set(BASE_HOURS)
    for row in series_rows(channel_id):
        if (
            row.get("kind") == "slots"
            and _active(row, when)
            and names_any(title or "", _names(row))
        ):
            hours.update(int(h) for h in row.get("extra_hours") or [])
    return tuple(sorted(hours))


def launch_names(channel_id: str, day: str | date) -> list[str]:
    """#1867: the names whose stories jump the queue today - an active `slots` row's."""
    when = _day(day)
    out: list[str] = []
    for row in series_rows(channel_id):
        if row.get("kind") == "slots" and _active(row, when):
            out.extend(_names(row))
    return out


def jump_first(ideas: list[Any], names: list[str]) -> list[Any]:
    """#1867: the first headline naming one of `names` on `JUMP_OUTLETS`+ outlets goes first."""
    if not names:
        return ideas
    from apis.topic_tokens import names_any

    for i, bet in enumerate(ideas):
        if (
            getattr(bet, "source", "") == "trending"
            and int(getattr(bet, "outlets", 0) or 0) >= JUMP_OUTLETS
            and names_any(str(getattr(bet, "topic", "") or ""), names)
        ):
            return [bet, *ideas[:i], *ideas[i + 1 :]]
    return ideas


def dated_ideas(
    channel_id: str,
    *,
    now: datetime | None = None,
    headlines: Callable[[str, dict[str, Any], datetime], list[dict[str, Any]]] | None = None,
    notes: list[str] | None = None,
) -> list[Any]:
    """The day's `moment` and `long` entries as ideas (BestBetResult, source = the kind), not
    yet drafted. `notes` gets why an entry due today was skipped."""
    if not dated_enabled():
        return []
    from apis.topic_tokens import names_any
    from core.batch_generation import series_drafted
    from core.best_bet import BestBetResult

    moment = now or datetime.now(timezone.utc)
    today = channel_day(channel_id, moment)
    out: list[Any] = []
    lines: list[dict[str, Any]] | None = None
    for row in series_rows(channel_id):
        kind = str(row.get("kind") or "")
        if kind not in _FACTS or not row.get("on") or not row.get("topic"):
            continue
        try:
            due = _day(row["on"]) == today
        except ValueError:
            continue
        topic = str(row["topic"])
        if not due or series_drafted(channel_id, topic):
            continue
        if lines is None:
            lines = (headlines or feed_headlines)(channel_id, row, moment)
        names = _names(row)
        needs = [str(w) for w in row.get("needs") or [] if str(w).strip()]
        if needs:  # the titles, not the outlets: "PC Gamer reported" names no PC question
            week = subject_headlines(names, lines, now=moment, hours=_NEEDS_HOURS)
            if not any(names_any(str(item.get("title") or ""), needs) for item in week):
                if notes is not None:
                    notes.append(f'"{topic}" skipped - no {row.get("subject")} headline this '
                                 f"week names {' or '.join(needs)}")  # fmt: skip
                continue
        hours, limit = _FACTS[kind]
        facts = headline_facts(names, lines, now=moment, hours=hours, limit=limit)
        out.append(
            BestBetResult(
                topic=topic,
                domain=str(row.get("domain") or "gaming"),
                avg_engaged_rate=0.0,
                source=kind,
                supporting_runs=0,
                rationale=f"series · {row.get('subject')} {kind} for {today:%b} {today.day}"
                + (" - a long video, after your review" if kind == "long" else ""),
                facts=facts,
                draft_kind="long" if kind == "long" else "",
                publish_at=str(row.get("publish_at") or ""),
            )
        )
    return out
