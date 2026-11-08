"""#1686 (B04.15, wave 156): "Who is ...?" in 45 s for a name that just trended.

A name the last 48 hours' headlines carry on `WHO_OUTLETS`+ distinct outlets, that is not on the
marquee list, that Wikipedia describes as a person (an athlete, a fighter, a coach, a streamer ...),
whose pageviews just rose (the last 3 days' average at `WHO_RISE`x the 7 before) and that a casual
fan does not know yet (under `KNOWN_FLOOR` views in 30 days - #1605's floor: a known name is a
subject, not a "who is"). Live 11-06: Josh Hokit, UFC 334's main event, on 5 outlets, 72,794
views in 30 days and rising 2.1x. One a night, drafted once, at the Short preset (45 s), with
the headlines and Wikipedia's description as its facts. `WHO_IS=false` turns it off (the suite).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.series.profiles")

WHO_OUTLETS = 3
WHO_HOURS = 48.0
WHO_RISE = 1.5
LOOKUPS = 3  # names read from Wikipedia a night - two reads each
_PERSON = re.compile(
    r"\b(player|footballer|quarterback|linebacker|receiver|running back|cornerback|safety|"
    r"basketball|baseball|hockey|soccer|fighter|martial artist|boxer|wrestler|athlete|coach|"
    r"manager|streamer|youtuber|content creator|rapper|singer|actor|actress|musician|golfer|"
    r"tennis|racing driver|esports|gamer|game designer|game developer)\b",
    re.IGNORECASE,
)


_PLACE = re.compile(
    r"\b(city|county|state|stadium|arena|park|garden|gardens|center|centre|island|valley|bay|"
    r"beach|street|square|airport|university|college|league|conference|division|house|"
    r"results?|night|card|cup|bowl|awards?|games?|series|championships?|current|united|fc|"
    r"club|team|tour|open|show|week|weekend|day)$",
    re.IGNORECASE,
)


def enabled() -> bool:
    return os.getenv("WHO_IS", "true").strip().lower() not in ("0", "false", "no", "off")


def _when(row: dict[str, Any]) -> datetime | None:
    first = row.get("first") or row.get("published")
    if not isinstance(first, datetime):
        return None
    return first if first.tzinfo else first.replace(tzinfo=timezone.utc)


def trending_names(
    pool: list[dict[str, Any]], names: list[str], *, now: datetime
) -> list[tuple[str, str, int, list[str]]]:
    """(name, article, outlets, headlines) for each name of two or three words the last
    `WHO_HOURS` of headlines carry on `WHO_OUTLETS`+ distinct outlets, most outlets first - a
    marquee name and a death story left out."""
    from apis.topic_tokens import names_any
    from apis.wikipedia_pageviews_api import subject_articles
    from core.authenticity import is_death_story

    outlets: dict[str, set[str]] = {}
    heads: dict[str, list[str]] = {}
    articles: dict[str, str] = {}
    horizon = now - timedelta(hours=WHO_HOURS)
    for row in pool:
        topic = str(row.get("topic") or "")
        when = _when(row)
        if not topic or when is None or not horizon <= when <= now or is_death_story(topic):
            continue
        carried = {str(o) for o in (row.get("outlets") or []) if o} or {
            str(row.get("source") or topic)
        }
        for name, article in subject_articles(topic):
            if names_any(name, names) or any(names_any(n, [name]) for n in names):
                continue
            outlets.setdefault(name, set()).update(carried)
            heads.setdefault(name, []).append(topic)
            articles[name] = article
    found = [
        (n, articles[n], len(o), heads[n]) for n, o in outlets.items() if len(o) >= WHO_OUTLETS
    ]
    # #2009, live 11-06: "New York City" and "York City" ranked beside Josh Hokit and took the
    # night's lookups - a phrase inside a longer one found is dropped, and a name ending on a
    # place or event word goes after the people (live 11-07: "Main Card Results", "UFC Fight
    # Night" and "White House" led Cortes Acosta)
    longer = [n for n, *_rest in found]
    found = [f for f in found if not any(f[0] != o and f[0].lower() in o.lower() for o in longer)]
    return sorted(found, key=lambda item: (bool(_PLACE.search(item[0])), -item[2]))


def who_is_topic(name: str) -> str:
    return f"Who is {name}?"


def profile_ideas(
    channel_id: str,
    *,
    now: datetime | None = None,
    pool: list[dict[str, Any]] | None = None,
    read: Callable[[str], dict | None] | None = None,
    describe: Callable[[str], str] | None = None,
) -> list[Any]:
    """At most one "Who is ...?" idea (source "profile") for tonight, or []. Never raises."""
    if not enabled():
        return []
    try:
        from apis import wikipedia_pageviews_api as wiki
        from core.batch_generation import series_drafted
        from core.best_bet import BestBetResult, marquee_names

        moment = now or datetime.now(timezone.utc)
        if pool is None:
            from jobs.fast_lane import _pool

            pool = _pool(channel_id)
        views_of = read or wiki.thirty_days
        description_of = describe or wiki.page_description
        for name, article, count, headlines in trending_names(
            pool, marquee_names(channel_id), now=moment
        )[:LOOKUPS]:
            topic = who_is_topic(name)
            if series_drafted(channel_id, topic):
                continue
            seen = views_of(article) or {}
            views, rise = int(seen.get("views") or 0), float(seen.get("rise") or 0.0)
            if not views or views >= wiki.KNOWN_FLOOR or rise < WHO_RISE:
                continue
            described = description_of(article)
            if not _PERSON.search(described or ""):
                continue
            facts = [f"Wikipedia describes {name} as: {described}.",
                     *(f"A headline this week: {h}" for h in headlines[:4])]  # fmt: skip
            return [BestBetResult(
                topic=topic, domain=_domain(pool, headlines), avg_engaged_rate=0.0,
                source="profile", supporting_runs=0, facts=facts, outlets=count,
                rationale=(f"who is · {name} on {count} outlets in {WHO_HOURS:g} h, Wikipedia "
                           f"views up {rise:.1f}x - who they are and why now, in 45 s"),
            )]  # fmt: skip
        return []
    except Exception as exc:
        logger.debug("who-is ideas skipped: %s", exc)
        return []


def _domain(pool: list[dict[str, Any]], headlines: list[str]) -> str:
    for row in pool:
        if str(row.get("topic") or "") in headlines and row.get("domain"):
            return str(row["domain"])
    return "neutral"
