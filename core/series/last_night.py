"""Last night's games as the morning's ideas (wave 153) - read by overnight at 05:00.

- #1999: a national final the fast lane did not make. The worker runs only while the PC is awake
  (no wake timers - the operator, 2026-11-06), and its 05:07 pass is held while overnight runs, so
  the TNF final of 11-05 was never seen. A national NFL or NBA final within `SLEPT_HOURS` of its
  expected end becomes a result Short - "what it means" (decision 76) - public at the next slot.
- #1877 (B12.6): a marquee name's 40-point night (`BIG_NIGHT`) on last night's NBA board, from
  ESPN's game leaders, national game or not - the player, the points and the final.
- #1687 (B04.16): "what's next" - each team's next game, from ESPN's schedules, rides along as a
  key fact, so the result's call is about a game that is on the calendar. The fast lane's results
  carry them too (`fast_lane.story_facts`).

At most `MAX_IDEAS` a night, a game once, never one the fast lane made or a story drafted.
`LAST_NIGHT=false` stops it (the suite does).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from core.logging import get_logger

logger = get_logger("core.series.last_night")

SLEPT_HOURS = 12.0
BIG_NIGHT = 40
MAX_IDEAS = 2
_EASTERN = ZoneInfo("America/New_York")  # ESPN dates a game by its US evening


def enabled() -> bool:
    return os.getenv("LAST_NIGHT", "true").strip().lower() not in ("0", "false", "no", "off")


def _events(
    fetch: Callable[..., dict[str, Any]], now: datetime
) -> list[tuple[str, dict[str, Any]]]:
    """(league, event) for the NFL's week board and the NBA's boards of last night and today."""
    seen: set[str] = set()
    out: list[tuple[str, dict[str, Any]]] = []
    days = dict.fromkeys(
        f"{(now - timedelta(hours=h)).astimezone(_EASTERN):%Y%m%d}" for h in (SLEPT_HOURS, 0)
    )
    reads: list[tuple[str, dict[str, Any]]] = [("nfl", {})]
    reads += [("nba", {"dates": day}) for day in days]
    for league, params in reads:
        try:
            board = fetch(league, **params) or {}
        except Exception as exc:
            logger.debug("last night: %s board unread: %s", league, exc)
            continue
        for event in board.get("events") or []:
            key = (
                f"{league}:{event.get('id') or event.get('name')}"
                if isinstance(event, dict)
                else ""
            )
            if key and key not in seen:
                seen.add(key)
                out.append((league, event))
    return out


def _leader(side: dict[str, Any]) -> tuple[str, int]:
    """The side's points leader and his points, from ESPN's game leaders."""
    for group in side.get("leaders") or []:
        if not isinstance(group, dict) or group.get("name") != "points":
            continue
        top = next(iter(group.get("leaders") or []), None) or {}
        try:
            points = int(float(top.get("value") or top.get("displayValue") or 0))
        except (TypeError, ValueError):
            points = 0
        return str((top.get("athlete") or {}).get("displayName") or ""), points
    return "", 0


def big_night(event: dict[str, Any], names: list[str], *, now: datetime) -> dict[str, Any] | None:
    """#1877: a marquee name's `BIG_NIGHT`-point game, final, within `SLEPT_HOURS` of its end."""
    from apis.topic_tokens import names_any
    from jobs.fast_lane import GAME_HOURS, _side

    if ((event.get("status") or {}).get("type") or {}).get("completed") is not True:
        return None
    try:
        start = datetime.fromisoformat(str(event.get("date") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    end = start + timedelta(hours=GAME_HOURS["nba"])
    if not start < now <= end + timedelta(hours=SLEPT_HOURS):
        return None
    comp = (event.get("competitions") or [{}])[0]
    sides = {key: _side(comp, key) for key in ("away", "home")}
    try:
        score = {key: int(str(side.get("score"))) for key, side in sides.items()}
    except (TypeError, ValueError):
        return None
    team = {
        key: str((side.get("team") or {}).get("shortDisplayName") or "")
        for key, side in sides.items()
    }
    for key, side in sides.items():
        player, points = _leader(side)
        if points < BIG_NIGHT or not player or not names_any(player, names):
            continue
        other = "home" if key == "away" else "away"
        won = score[key] > score[other]
        high, low = max(score.values()), min(score.values())
        verb = "beat" if won else "fall to"
        return {
            "kind": "big_night",
            "key": f"big:{event.get('id') or event.get('name')}",
            "result_key": f"result:{event.get('id') or event.get('name')}",
            "league": "nba",
            "topic": f"{player} scores {points} as the {team[key]} {verb} the {team[other]} "
                     f"{high}-{low}: what it means",
            "final": f"ESPN final: {team['away']} {score['away']}, {team['home']} {score['home']} - "
                     f"{team[key] if won else team[other]} won",
            "lines": [f"{player} scored {points} points (ESPN's game leaders)."],
            "teams": [{"abbr": str((s.get("team") or {}).get("abbreviation") or ""),
                       "name": team[k]} for k, s in sides.items()],
        }  # fmt: skip
    return None


_SCORE = re.compile(r"\b\d{1,3}-\d{1,3}\b")


def result_drafted(channel_id: str, topic: str, *, recent: list[str] | None = None) -> bool:
    """A result of this game already drafted - a recent topic with a score naming the same game,
    or this very topic waiting. The game's preview is not its result: live 11-06, run 242
    ("Jacksonville Jaguars at Baltimore Ravens") read as the same story and kept the TNF final
    the PC slept through from being drafted."""
    from core.best_bet import same_story

    if recent is None:
        from core.batch_generation import unreviewed_draft
        from core.channel_context import recent_input_topics

        if unreviewed_draft(channel_id, topic) is not None:
            return True
        recent = list(recent_input_topics(channel_id, limit=30))
    results = [t for t in recent if _SCORE.search(str(t or ""))]
    return bool(results) and same_story(topic, results)


def next_game_lines(
    league: str,
    teams: list[dict[str, str]],
    *,
    now: datetime,
    channel_id: str = "tapin",
    schedule: Callable[[str, str], dict[str, Any]] | None = None,
) -> list[str]:
    """#1687: "ESPN schedule: the Ravens play the Chargers next, on Monday, November 16." - each
    team's next game in the channel's zone. [] for a team ESPN gives no next game."""
    if schedule is None:
        from sports.espn import get_schedule

        schedule = get_schedule
    read_schedule: Callable[[str, str], dict[str, Any]] = schedule
    from core.series.dated import channel_zone

    zone = channel_zone(channel_id)
    lines: list[str] = []
    for team in teams or []:
        abbr, name = str(team.get("abbr") or ""), str(team.get("name") or "")
        if not abbr or not name:
            continue
        try:
            events = (read_schedule(league, abbr) or {}).get("events") or []
        except Exception as exc:
            logger.debug("schedule for %s unread: %s", abbr, exc)
            continue
        for event in events:
            try:
                when = datetime.fromisoformat(str(event.get("date") or "").replace("Z", "+00:00"))
            except ValueError:
                continue
            when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
            if when <= now:
                continue
            comp = (event.get("competitions") or [{}])[0]
            opponent = next((str((c.get("team") or {}).get("shortDisplayName") or "")
                             for c in comp.get("competitors") or []
                             if str((c.get("team") or {}).get("abbreviation") or "") != abbr), "")  # fmt: skip
            if opponent:
                local = when.astimezone(zone)
                lines.append(f"ESPN schedule: the {name} play the {opponent} next, on "
                             f"{local:%A}, {local:%B} {local.day}.")  # fmt: skip
            break
    return lines


def last_night_ideas(
    channel_id: str,
    *,
    now: datetime | None = None,
    fetch: Callable[..., dict[str, Any]] | None = None,
    schedule: Callable[[str, str], dict[str, Any]] | None = None,
    done: set[str] | None = None,
    drafted: Callable[[str], bool] | None = None,
) -> list[Any]:
    """The night's result ideas (source "result"), a 40-point night first. Never raises."""
    if not enabled():
        return []
    try:
        from core.best_bet import BestBetResult, marquee_names
        from jobs import fast_lane

        moment = now or datetime.now(timezone.utc)
        if fetch is None:
            from sports.espn import get_scoreboard

            fetch = get_scoreboard
        read_board: Callable[..., dict[str, Any]] = fetch
        if done is None:
            done = set(fast_lane.load_store(channel_id).get("done") or [])
        if drafted is None:

            def drafted(topic: str) -> bool:
                return result_drafted(channel_id, topic)

        names = marquee_names(channel_id)
        found: list[dict[str, Any]] = []
        for league, event in _events(read_board, moment):
            if not isinstance(event, dict):
                continue
            story = big_night(event, names, now=moment) if league == "nba" else None
            if story is None:
                final = fast_lane.final_of(league, event, now=moment, fresh_hours=SLEPT_HOURS)
                story = dict(final, result_key=final["key"], lines=[]) if final else None
            if story is None or {story["key"], story["result_key"]} & done:
                continue
            if drafted(story["topic"]):
                continue
            found.append(story)
        found.sort(key=lambda s: s["kind"] != "big_night")
        ideas: list[Any] = []
        for story in found[:MAX_IDEAS]:
            facts = [story["final"], *story["lines"],
                     *next_game_lines(story["league"], story.get("teams") or [], now=moment,
                                      channel_id=channel_id, schedule=schedule)]  # fmt: skip
            ideas.append(BestBetResult(
                topic=story["topic"], domain=story["league"], avg_engaged_rate=0.0,
                source="result", supporting_runs=0, facts=facts,
                rationale=f"last night · {story['final']} - the fast lane did not make it",
            ))  # fmt: skip
        return ideas
    except Exception as exc:
        logger.debug("last night's ideas skipped: %s", exc)
        return []
