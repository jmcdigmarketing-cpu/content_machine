"""#1847 (B11.1): "GTA 6: N days to launch" - a daily countdown Short to a dated launch.

Modelled on "Picks, graded" (#991): `countdown_idea` is the day's idea - the topic, the lines it is
written from - and `best_bet.get_idea_menu` puts it first, as an extra idea; overnight drafts it
on top of the night's count (the operator, 2026-10-28: "an extra fourth"). Its facts are the day's
headlines naming the subject, else the date alone. The title is the stem then the day's story
(`series_title`); the day's end is its deadline, so a countdown is held and retired after it the
way a preview is after its game - its number would be wrong.

`config/series.json` holds the rows; `SERIES_COUNTDOWN=false` switches it off (the suite does).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Any

from core.logging import get_logger

logger = get_logger("core.series.countdown")

_SERIES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "series.json",
)
_FACT_HEADLINES = 5
_FRESH_HOURS = 24
_TITLE_LIMIT = 100  # YouTube's


def countdown_enabled() -> bool:
    from core.providers import flag_enabled

    return flag_enabled("SERIES_COUNTDOWN", default=True)


def series_rows(channel_id: str) -> list[dict[str, Any]]:
    """The channel's series rows from `config/series.json`, [] when unread."""
    try:
        with open(_SERIES_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        logger.debug("series.json unread: %s", exc)
        return []
    rows = data.get(channel_id) if isinstance(data, dict) else None
    return [r for r in rows or [] if isinstance(r, dict) and r.get("kind")]


def channel_zone(channel_id: str) -> tzinfo:
    """The channel's timezone - a countdown's day is the viewer's day, not the PC's or UTC."""
    try:
        from zoneinfo import ZoneInfo

        from analytics.post_timing import _load_static_post_schedule

        return ZoneInfo(_load_static_post_schedule(channel_id).timezone)
    except Exception as exc:
        logger.debug("channel zone unread for %s: %s", channel_id, exc)
        return timezone.utc


def days_left(day: str | date, until: str | date) -> int:
    return (_day(until) - _day(day)).days


def countdown_topic(title: str, *, day: str, start: str, until: str) -> str:
    """The day's topic - `title` with {n} the days to `until` - from `start` to the day before
    `until`, else "". One day is "1 day" (the brief: "GTA 6: 1 day to launch")."""
    if not (_day(start) <= _day(day) < _day(until)):
        return ""
    n = days_left(day, until)
    text = str(title).replace("{n}", str(n))
    return text.replace("1 days", "1 day") if n == 1 else text


def series_title(stem: str, title: str, *, limit: int = _TITLE_LIMIT) -> str:
    """#1847 (the operator, 2026-10-28: the stem, then the story): "GTA 6: 21 days to launch -
    <the generated title>", the stem alone when both do not fit in `limit` characters."""
    title = " ".join(str(title or "").split())
    stem = " ".join(str(stem or "").split())
    if not stem:
        return title
    if not title:
        return stem
    if title.lower().startswith(stem.lower()):
        return title
    joined = f"{stem} - {title}"
    return joined if len(joined) <= limit else stem


def day_deadline(day: date, zone: tzinfo) -> str:
    """The next local midnight after `day`, ISO UTC - the countdown's number is wrong after it."""
    midnight = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=zone)
    return midnight.astimezone(timezone.utc).isoformat()


def countdown_facts(
    row: dict[str, Any], day: date, headlines: list[dict[str, Any]], *, now: datetime
) -> list[str]:
    """The date line, then up to five of the last day's headlines naming the subject."""
    until = _day(row["until"])
    n = days_left(day, until)
    unit = "day" if n == 1 else "days"
    subject = str(row.get("subject") or "").strip()
    names = [str(name) for name in row.get("names") or [subject] if str(name).strip()]
    return [
        f"{subject} launches on {until:%B} {until.day}, {until.year} - {n} {unit} from "
        f"{day:%B} {day.day}.",
        *headline_facts(names, headlines, now=now, hours=_FRESH_HOURS, limit=_FACT_HEADLINES),
    ]


def subject_headlines(
    names: list[str], headlines: list[dict[str, Any]], *, now: datetime, hours: float
) -> list[dict[str, Any]]:
    """The dated headlines of the last `hours` naming one of `names`, each title once. An
    undated headline may be old news, so it is left out."""
    from apis.topic_tokens import names_any

    horizon = now - timedelta(hours=hours)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in headlines:
        title = " ".join(str(item.get("title") or "").split())
        published = item.get("published")
        if not title or not isinstance(published, datetime):
            continue
        stamp = published if published.tzinfo else published.replace(tzinfo=timezone.utc)
        if stamp < horizon or not names_any(title, names) or title.lower() in seen:
            continue
        seen.add(title.lower())
        out.append({**item, "title": title})
    return out


def headline_facts(
    names: list[str], headlines: list[dict[str, Any]], *, now: datetime, hours: float, limit: int
) -> list[str]:
    """Up to `limit` of `subject_headlines` as fact lines - "Dexerto reported: <title>"."""
    found = subject_headlines(names, headlines, now=now, hours=hours)
    return [
        f"{item.get('source') or 'A source'} reported: {item['title']}" for item in found[:limit]
    ]


def countdown_playlist(channel_id: str, title: str) -> str:
    """#1855: the playlist a countdown title belongs to in day order ("GTA"), else ""."""
    for row in series_rows(channel_id):
        template = str(row.get("title") or "")
        if row.get("kind") != "countdown" or "{n}" not in template or not row.get("playlist"):
            continue
        pattern = re.escape(template).replace(re.escape("{n}"), r"\d+").replace("days", "days?")
        if re.match(pattern, str(title or "").strip(), flags=re.IGNORECASE):
            return str(row["playlist"])
    return ""


def feed_headlines(channel_id: str, row: dict[str, Any], _now: datetime) -> list[dict[str, Any]]:
    """The channel's and the row's domain's feeds, as {title, source, published} - the feeds the
    idea pool reads (`best_bet.idea_feeds`). [] when they cannot be read."""
    try:
        from core.best_bet import _fetch_feeds, _parse_pubdate, idea_feeds

        feeds = idea_feeds(channel_id, {str(row.get("domain") or "gaming")})
        out: list[dict[str, Any]] = []
        for feed, items in zip(feeds, _fetch_feeds(feeds), strict=True):
            for item in items[:30]:
                out.append(
                    {
                        "title": str(item.get("title") or ""),
                        "source": str(feed.get("name") or "RSS"),
                        "published": _parse_pubdate(item.get("published")),
                    }
                )
        return out
    except Exception as exc:
        logger.debug("countdown headlines unread: %s", exc)
        return []


def countdown_idea(
    channel_id: str,
    *,
    now: datetime | None = None,
    headlines: Callable[[str, dict[str, Any], datetime], list[dict[str, Any]]] | None = None,
) -> Any:
    """The day's countdown idea (a `BestBetResult`, source "countdown"), or None - before its
    first day, from launch day on (#1848's), once it is drafted, or with SERIES_COUNTDOWN off."""
    if not countdown_enabled():
        return None
    from core.batch_generation import series_drafted
    from core.best_bet import BestBetResult

    moment = now or datetime.now(timezone.utc)
    zone = channel_zone(channel_id)
    day = moment.astimezone(zone).date()
    for row in series_rows(channel_id):
        if row.get("kind") != "countdown" or not row.get("from") or not row.get("until"):
            continue
        topic = countdown_topic(
            str(row["title"]), day=day.isoformat(), start=str(row["from"]), until=str(row["until"])
        )
        if not topic or series_drafted(channel_id, topic):
            continue
        lines = (headlines or feed_headlines)(channel_id, row, moment)
        facts = countdown_facts(row, day, lines, now=moment)
        n = days_left(day, row["until"])
        return BestBetResult(
            topic=topic,
            domain=str(row.get("domain") or "gaming"),
            avg_engaged_rate=0.0,
            source="countdown",
            supporting_runs=0,
            rationale=(
                f"series · {row.get('subject')} countdown - {n} day{'s' if n != 1 else ''} left, "
                f"{len(facts) - 1} headline(s) today"
            ),
            facts=facts,
            title_stem=topic,
            deadline=day_deadline(day, zone),
        )
    return None


def _day(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
