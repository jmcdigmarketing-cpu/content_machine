"""#1724 (B06.3, wave 149): one long explainer per marquee franchise, each new season.

A `season` row of `config/series.json` names a franchise ("Marvel Rivals"), the names a headline
uses for it, a `topic` with `{season}` in it ("Everything in Marvel Rivals {season}") and its
`search_terms`. When the franchise's headlines of the last `SEASON_HOURS` name a season ("Season
5", "Chapter 7 Season 1") on `SEASON_OUTLETS` or more outlets, that season's explainer is drafted
long - rendered only after your review, public at the weekly long slot (#1727) - once: the topic
carries the season, so `series_drafted` finds it the next night.

No date is kept by hand: a season is drafted when the outlets say it is here. Measured 11-04:
none of 244 gaming headlines from 12 feeds named a season - a launch week is when they do.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from core.logging import get_logger
from core.series.countdown import headline_facts, subject_headlines

logger = get_logger("core.series.seasons")

SEASON_HOURS = 72
SEASON_OUTLETS = 2
_FACT_HOURS, _FACT_LINES = 24 * 7, 12  # a long row's (dated._FACTS["long"])
# "Season 5", "Season 4.5", "Chapter 7 Season 1", "Chapter 7, Season 1" - never "Season 2026".
_SEASON_RE = re.compile(
    r"\b(?:chapter\s+(\d{1,2})\s*[,:-]?\s*)?season\s+(\d{1,2})(?:\.(5))?(?![\d.])", re.IGNORECASE
)


def season_label(title: str) -> tuple[tuple[int, int, int], str] | None:
    """(sort key, "Chapter 7 Season 1") for the season a headline names, or None."""
    found = _SEASON_RE.search(title or "")
    if not found:
        return None
    chapter, season, half = found.group(1), int(found.group(2)), found.group(3)
    label = (f"Chapter {int(chapter)} " if chapter else "") + f"Season {season}"
    label += ".5" if half else ""
    return (int(chapter or 0), season, 1 if half else 0), label


def latest_season(
    names: list[str],
    headlines: list[dict[str, Any]],
    *,
    now: datetime,
    hours: float = SEASON_HOURS,
    outlets: int = SEASON_OUTLETS,
) -> str:
    """The newest season the franchise's headlines name on `outlets`+ outlets, or ""."""
    seen: dict[str, tuple[tuple[int, int, int], set[str]]] = {}
    for item in subject_headlines(names, headlines, now=now, hours=hours):
        found = season_label(str(item.get("title") or ""))
        if found is None:
            continue
        key, label = found
        seen.setdefault(label, (key, set()))[1].add(str(item.get("source") or "").lower())
    passing = [(key, label) for label, (key, sources) in seen.items() if len(sources) >= outlets]
    return max(passing)[1] if passing else ""


def season_drafted(channel_id: str, topic: str) -> bool:
    """A season's explainer is made once: a waiting draft, or any run with its topic - not only
    the last 60 runs `series_drafted` reads (ten days), since a season's headlines run on."""
    from core.batch_generation import series_drafted
    from storage.repositories.content_runs import get_content_run_repository

    if series_drafted(channel_id, topic):
        return True
    key = " ".join(topic.lower().split())
    try:
        runs = get_content_run_repository().list_for_channel(channel_id)
    except Exception as exc:
        logger.debug("season runs unread: %s", exc)
        return True  # unread: never risk a second explainer
    for run in runs:
        seed = str(getattr(run, "input_topic", "") or getattr(run, "selected_topic", "") or "")
        if " ".join(seed.lower().split()) == key:
            return True
    return False


def season_idea(row: dict[str, Any], headlines: list[dict[str, Any]], *, now: datetime) -> Any:
    """The row's explainer for the season its headlines name (a `BestBetResult`, source "season",
    drafted long), or None while no season is named on two outlets."""
    from core.best_bet import BestBetResult

    names = [str(n) for n in row.get("names") or [row.get("subject")] if n]
    template = str(row.get("topic") or "")
    if not names or "{season}" not in template:
        return None
    label = latest_season(names, headlines, now=now)
    if not label:
        return None
    facts = headline_facts(names, headlines, now=now, hours=_FACT_HOURS, limit=_FACT_LINES)
    return BestBetResult(
        topic=template.format(season=label),
        domain=str(row.get("domain") or "gaming"),
        avg_engaged_rate=0.0,
        source="season",
        supporting_runs=0,
        rationale=f"series · {row.get('subject')} {label} explainer - a long video, after your "
        "review, public at the weekly long slot",
        facts=facts,
        draft_kind="long",
    )
