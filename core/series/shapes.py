"""Wave 157: three formats a draft takes from its story - each recorded on the run (`shape`) so the
weekly format ranking (`core/success/formats.py`) can keep or drop it (B04: "each recorded and
rotated out when it underperforms").

- #1676 (B04.5) stat-shock: a headline built on one surprising number - "historic 52-point,
  24-rebound night", "Fall Below 20 Percent ... For First Time" - is written with that number as the
  whole video.
- #1674 (B04.3) ranking: "Top 5 ...", "Ranking the 7 worst ...", "Every GTA Game, Ranked" is written
  as a countdown from five (at most) to one, each item "Number N"; the captions put each number on
  screen while it is the one being told (`video/subtitles._with_countdown`).
- #1688 (B04.17) patch winners and losers: a Marvel Rivals or Call of Duty patch, update or
  balance headline becomes "<game> patch: the winners and losers" (`patch_ideas`, source "patch"),
  once a patch, from the headlines that name it. `PATCH_SHORTS=false` stops the idea.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.series.shapes")

COUNTDOWN_MAX = 5  # a Short counts down five at most

_NUMBER_WORDS = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                 "ten": 10}  # fmt: skip
_N = r"(\d{1,2}|three|four|five|six|seven|eight|nine|ten)"
_RANKING = re.compile(
    rf"^\s*(?:the\s+)?top\s+{_N}\b|\branking\s+the\s+{_N}\b|^\s*{_N}\s+(?:best|worst|biggest|greatest|"
    r"most|devastating|underrated|overrated|craziest|wildest)\b|"
    # "Every GTA Game, Ranked" - not "ranked mode", "ranked No. 1" or a roundup's ranking
    r"^\s*(?:every|all)\b.*\branked\b|,\s*ranked\b|\branked\s*$",
    re.IGNORECASE,
)
_ROUNDUP = re.compile(r"\bpower\s+rankings?\b|;", re.IGNORECASE)
_SHOCK_NUMBER = re.compile(
    r"\b\d{2,3}-(?:point|rebound|assist|yard|catch|strikeout|goal|save|win|loss|game)\b|"
    r"\b\d+(?:\.\d+)?\s?(?:million|billion)\b|\$\d[\d,.]*|\b\d+(?:-| )seconds?\b|"
    r"\b\d+(?:\.\d+)?\s?(?:%|percent)\b",
    re.IGNORECASE,
)
_ANY_NUMBER = re.compile(r"\b\d[\d,.]*\b")
_SHOCK_WORD = re.compile(
    r"\b(record|historic|first time|first ever|most ever|fastest|youngest|oldest|never before|"
    r"all-time|unprecedented)\b",
    re.IGNORECASE,
)
_NUMBERED_EVENT = re.compile(r"\b(?:UFC|Week|Season|Game|Round|No\.)\s+\d+\b", re.IGNORECASE)

PATCH_GAMES = {
    "Marvel Rivals": re.compile(r"\bmarvel rivals\b", re.IGNORECASE),
    "Call of Duty": re.compile(
        r"\b(call of duty|black ops( \d| [ivx]+)?|warzone|modern warfare|cod)\b", re.IGNORECASE
    ),
}
_PATCH_WORD = re.compile(
    r"\b(patch(?: notes)?|update|hotfix|buffs?|nerfs?|balance changes?|mid-season)\b", re.IGNORECASE
)
PATCH_HOURS = 72.0


def ranking_count(topic: str) -> int:
    """How many a countdown of `topic` counts down from (at most `COUNTDOWN_MAX`), or 0 when it is
    not a ranking. "Every GTA Game, Ranked" counts five; a news roundup's "Power Rankings" none."""
    text = topic or ""
    found = _RANKING.search(text)
    if found is None or _ROUNDUP.search(text):
        return 0
    raw = next((g for g in found.groups() if g), "")
    n = int(raw) if raw.isdigit() else _NUMBER_WORDS.get(raw.lower(), COUNTDOWN_MAX)
    return min(COUNTDOWN_MAX, n) if n >= 3 else 0


def shock_number(topic: str) -> str:
    """The one surprising number a headline is built on - a stat with its unit ("52-point"), a
    money or magnitude figure, a share, a count of seconds, or any number beside a record word -
    else "". A numbered event ("UFC 334", "Week 9") is not one."""
    text = _NUMBERED_EVENT.sub(" ", topic or "")
    found = _SHOCK_NUMBER.search(text)
    if found:
        return found.group(0).strip()
    if _SHOCK_WORD.search(text):
        number = _ANY_NUMBER.search(text)
        if number:
            return number.group(0)
    return ""


def patch_game(topic: str) -> str:
    """The game a patch headline is about (Marvel Rivals, Call of Duty), else ""."""
    if not _PATCH_WORD.search(topic or ""):
        return ""
    return next((game for game, pattern in PATCH_GAMES.items() if pattern.search(topic or "")), "")


def draft_shape(topic: str, source: str = "") -> str:
    """The run's shape: "patch" (its menu source), "ranking", "stat_shock" or ""."""
    if source == "patch":
        return "patch"
    if ranking_count(topic):
        return "ranking"
    if shock_number(topic):
        return "stat_shock"
    return ""


def shape_brief(shape: str, topic: str) -> str:
    """The direction a shape gives the script, or ""."""
    if shape == "ranking":
        n = ranking_count(topic)
        return (f"RANKING: a countdown from {n} to 1 - each item opens its own sentence with "
                f"\"Number {n},\" then \"Number {n - 1},\" down to \"Number 1,\", each with one fact "
                "from the facts; Number 1 is the payoff and comes last. If the story ranks more, "
                f"count down its top {n}.")  # fmt: skip
    if shape == "stat_shock":
        number = shock_number(topic)
        return (f"STAT-SHOCK: one number is the whole video - {number}. Say it first, then what it "
                "is, the normal it beats (from a fact) and what it means. No other number competes "
                "with it.")  # fmt: skip
    if shape == "patch":
        return ("PATCH WINNERS AND LOSERS: the winners first, then the losers, each named with the "
                "change the facts give it; name no hero, weapon or number the facts do not. End on "
                "the one change that matters most.")  # fmt: skip
    return ""


def enabled() -> bool:
    return os.getenv("PATCH_SHORTS", "true").strip().lower() not in ("0", "false", "no", "off")


def patch_topic(game: str, headline: str) -> str:
    season = re.search(r"\bseason\s+\d+(?:\.\d+)?\b", headline or "", re.IGNORECASE)
    tag = f" {season.group(0).title()}" if season else ""
    return f"{game}{tag} patch: the winners and losers"


def patch_ideas(
    channel_id: str,
    *,
    now: datetime | None = None,
    pool: list[dict[str, Any]] | None = None,
    drafted: Callable[[str, str], bool] | None = None,
) -> list[Any]:
    """#1688: at most one "<game> patch: the winners and losers" idea for tonight, from the last
    `PATCH_HOURS` of headlines, or []. Never raises."""
    if not enabled():
        return []
    try:
        from core.batch_generation import series_drafted
        from core.best_bet import BestBetResult

        moment = now or datetime.now(timezone.utc)
        if pool is None:
            from jobs.fast_lane import _pool

            pool = _pool(channel_id)
        horizon = moment - timedelta(hours=PATCH_HOURS)
        by_game: dict[str, list[dict[str, Any]]] = {}
        for row in pool:
            topic = str(row.get("topic") or "")
            first = row.get("first") or row.get("published")
            if not isinstance(first, datetime):
                continue
            first = first if first.tzinfo else first.replace(tzinfo=timezone.utc)
            game = patch_game(topic)
            if game and horizon <= first <= moment:
                by_game.setdefault(game, []).append(row)
        seen = drafted or series_drafted
        for game, rows in by_game.items():
            topic = patch_topic(game, str(rows[0].get("topic") or ""))
            if seen(channel_id, topic):
                continue
            facts = [f"{', '.join(map(str, (r.get('outlets') or ['A source'])[:2]))} reported: "
                     f"{r['topic']}" for r in rows[:5]]  # fmt: skip
            return [BestBetResult(
                topic=topic, domain="gaming", avg_engaged_rate=0.0, source="patch",
                supporting_runs=0, facts=facts,
                outlets=len({str(o) for r in rows for o in (r.get("outlets") or [])}),
                rationale=f"patch · {game} - the winners and losers, from {len(rows)} headline(s)",
            )]  # fmt: skip
        return []
    except Exception as exc:
        logger.debug("patch ideas skipped: %s", exc)
        return []
