"""Local $0 seasonal seeds for best-bet — no HTTP, not a second cache.

Dated items (UFC cards, earnings weeks, game launches) live in
``config/seasonal_calendar.json``. Past dates are expired. Fail-open: missing
or corrupt file yields no seeds.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.seasonal_calendar")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today(now: datetime | None = None) -> date:
    stamp = now or _now()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.date()


def _path() -> str:
    from config.paths import SEASONAL_CALENDAR_FILE

    return SEASONAL_CALENDAR_FILE


def _load() -> dict[str, Any]:
    path = _path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.debug("seasonal calendar read failed: %s", exc)
        return {}


def due_topics(channel_id: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Items whose ``date`` is today for ``channel_id``. Expired dates omitted."""
    today = _today(now)
    payload = _load()
    rows = payload.get(channel_id) or payload.get("channels", {}).get(channel_id) or []
    if not isinstance(rows, list):
        return []
    due: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        day = str(raw.get("date") or "").strip()
        topic = str(raw.get("topic") or "").strip()
        if not day or not topic:
            continue
        try:
            item_day = date.fromisoformat(day)
        except ValueError:
            logger.debug("seasonal calendar skipped bad date %r", day)
            continue
        if item_day < today:
            continue
        if item_day != today:
            continue
        due.append(
            {
                "date": day,
                "topic": topic,
                "domain": str(raw.get("domain") or "").strip(),
            }
        )
    return due


# #1023: awards offered only while they are still ahead and inside three weeks.
AWARD_DATES = (
    (date(2026, 10, 28), "Ballon d'Or 2026", "soccer"),
    (date(2026, 12, 11), "The Game Awards 2026", "gaming"),
)
_WEEK = timedelta(days=7)
_AWARD_WINDOW = timedelta(days=21)
_BOARD_LEAGUES = ("nfl", "nba", "nhl", "mlb", "college-football", "soccer")


def _board_today() -> date:
    return date.today()


# #1151: each coming game's start, as its board wrote it. The week fetch fills it; a draft
# written from a schedule pick reads it, so the draft knows when its game is.
_STARTS: dict[str, str] = {}
# #1242/#1243: each kept game's broadcast, records and notes, by name - what makes a game worth a
# video, and what its idea says about it.
_DETAILS: dict[str, dict[str, Any]] = {}


def event_start(topic: str) -> str:
    """When the scheduled game named `topic` starts (the board's ISO time), or ""."""
    return _STARTS.get(str(topic or "").strip(), "")


def game_detail(league: str, event: dict[str, Any]) -> dict[str, Any]:
    """The league, kickoff, broadcasts, notes and each side's short name and record."""
    competitions = event.get("competitions") or [{}]
    comp = competitions[0] if isinstance(competitions, list) and competitions else {}
    comp = comp if isinstance(comp, dict) else {}
    sides: dict[str, dict[str, str]] = {}
    for side in comp.get("competitors") or []:
        if not isinstance(side, dict):
            continue
        team = side.get("team") or {}
        record = next(
            (str(r.get("summary")) for r in side.get("records") or [] if r.get("summary")), ""
        )
        name = str(team.get("shortDisplayName") or team.get("displayName") or "")
        sides[str(side.get("homeAway") or "")] = {"name": name, "record": record}
    # #1301: the board's own line ("GB -3.5") - free, where the odds signal lists only sports.
    odds = next((o for o in comp.get("odds") or [] if isinstance(o, dict)), {})
    return {
        "event_id": str(event.get("id") or ""),  # #1304: the summary and the result
        "line": str(odds.get("details") or ""),
        "total": str(odds.get("overUnder") or ""),
        "league": league,
        "date": str(event.get("date") or ""),
        "broadcasts": [
            str(n) for b in comp.get("broadcasts") or [] for n in (b.get("names") or []) if n
        ],
        "notes": [str(n.get("headline")) for n in comp.get("notes") or [] if n.get("headline")],
        "home": sides.get("home", {}),
        "away": sides.get("away", {}),
    }


_AWARD_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_AWARD_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def award_line(name: str) -> str:
    """When an award is given ("Wed Oct 28"), or "" when `name` is not one.

    English abbreviations, not `strftime`, so a non-English locale cannot rename
    the month (#1260).
    """
    wanted = (name or "").strip().lower()
    for when, title, _domain in AWARD_DATES:
        if title.lower() == wanted:
            return f"{_AWARD_DAYS[when.weekday()]} {_AWARD_MONTHS[when.month - 1]} {when.day}"
    return ""


def game_details(name: str) -> dict[str, Any]:
    """`game_detail` for a game read this run, or {} (an award, or a board not read)."""
    return dict(_DETAILS.get(name) or {})


def topics_from_board(
    league: str,
    board: dict[str, Any],
    *,
    today: date,
    starts: dict[str, str] | None = None,
    details: dict[str, dict[str, Any]] | None = None,
) -> list[tuple[str, str]]:
    """Games on this board that have not been played and fall inside the next week.

    `starts` (#1151) collects each kept game's start time by name; `details` (#1242) its
    broadcasts, records and notes.
    """
    horizon = today + _WEEK
    topics: list[tuple[str, str]] = []
    for event in (board or {}).get("events") or []:
        if not isinstance(event, dict):
            continue
        name = str(event.get("name") or "").strip()
        raw = str(event.get("date") or "")[:10]
        if not name or not raw:
            continue
        try:
            when = date.fromisoformat(raw)
        except ValueError:
            continue
        completed = ((event.get("status") or {}).get("type") or {}).get("completed") is True
        if completed or when < today or when > horizon:
            continue
        topics.append((name, league))
        if starts is not None:
            starts[name] = str(event.get("date") or "")
        if details is not None:
            details[name] = game_detail(league, event)
    return topics


def week_topics(
    boards: dict[str, Any],
    *,
    today: date,
    starts: dict[str, str] | None = None,
    details: dict[str, dict[str, Any]] | None = None,
) -> list[tuple[str, str]]:
    """Coming games plus award dates still inside the window."""
    topics: list[tuple[str, str]] = []
    for league, board in (boards or {}).items():
        if isinstance(board, dict):
            topics.extend(
                topics_from_board(str(league), board, today=today, starts=starts, details=details)
            )
    for when, name, domain in AWARD_DATES:
        if today <= when <= today + _AWARD_WINDOW:
            topics.append((name, domain))
    return topics


def schedule_enabled() -> bool:
    """Off in the suite (`BEST_BET_SCHEDULE=false`). On for a real run."""
    import os

    return os.getenv("BEST_BET_SCHEDULE", "true").strip().lower() not in ("0", "false", "no", "")


_UFC_DAYS = 14


def ufc_cards(
    board: dict[str, Any],
    *,
    now: datetime,
    days: int = _UFC_DAYS,
    starts: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    """The UFC cards of the next `days` from the board's calendar (decision 66), each start
    kept in `starts` so a draft knows when its card is (#1151)."""
    leagues = (board or {}).get("leagues") or [{}]
    calendar = (leagues[0] if isinstance(leagues[0], dict) else {}).get("calendar") or []
    horizon = now + timedelta(days=days)
    out: list[tuple[str, str]] = []
    for entry in calendar:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip()
        raw = str(entry.get("startDate") or "")
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if label and now <= when <= horizon:
            out.append((label, "ufc"))
            if starts is not None:
                starts[label] = raw
    return out


# #1286: every event read this run - played games and started cards too - by name, with its start,
# so a headline about one can be matched to it (run 160 named the card's two fighters).
_EVENTS: dict[str, str] = {}
_EVENT_DAYS_BACK = 3
_EVENT_DAYS_AHEAD = 14


def _start_of(raw: str) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def events_from_boards(
    boards: dict[str, Any], ufc_board: dict[str, Any] | None, *, now: datetime
) -> dict[str, str]:
    """{name: start} for each game on the boards and each UFC card, from a few days back to two
    weeks ahead - played and started ones included."""
    low = now - timedelta(days=_EVENT_DAYS_BACK)
    high = now + timedelta(days=_EVENT_DAYS_AHEAD)
    out: dict[str, str] = {}
    for board in (boards or {}).values():
        for event in (board or {}).get("events") or []:
            if not isinstance(event, dict):
                continue
            name, raw = str(event.get("name") or "").strip(), str(event.get("date") or "")
            when = _start_of(raw)
            if name and when is not None and low <= when <= high:
                out[name] = raw
    leagues = (ufc_board or {}).get("leagues") or [{}]
    calendar = (leagues[0] if isinstance(leagues[0], dict) else {}).get("calendar") or []
    for entry in calendar:
        if not isinstance(entry, dict):
            continue
        name, raw = str(entry.get("label") or "").strip(), str(entry.get("startDate") or "")
        when = _start_of(raw)
        if name and when is not None and low <= when <= high:
            out[name] = raw
    return out


def event_for(text: str, *, events: dict[str, str] | None = None) -> tuple[str, str]:
    """(name, start) of the event `text` names - two of its sides, or its only one - else
    ("", ""). The same rule keeps a covered event off the idea menu (`best_bet.same_story`)."""
    from core.best_bet import same_story

    pool = _EVENTS if events is None else events
    if events is None and not pool and schedule_enabled():
        fetch_week_topics()  # fills _EVENTS
        pool = _EVENTS
    if not (text or "").strip():
        return "", ""
    for name, start in pool.items():
        if same_story(name, [text]):
            return name, start
    return "", ""


def fetch_week_topics() -> list[tuple[str, str]]:
    """This week's boards. A league that cannot be read is skipped (debug, not a warning)."""
    if not schedule_enabled():
        return []
    from sports.espn import get_scoreboard

    today = _board_today()
    boards: dict[str, Any] = {}
    for league in _BOARD_LEAGUES:
        try:
            boards[league] = get_scoreboard(league)
        except Exception as exc:
            logger.debug("scoreboard skipped for %s: %s", league, exc)
    topics = week_topics(boards, today=today, starts=_STARTS, details=_DETAILS)
    now = datetime.now(timezone.utc)
    ufc_board: dict[str, Any] = {}
    try:  # decision 66: UFC cards are previews too
        ufc_board = get_scoreboard("ufc")
        cards = ufc_cards(ufc_board, now=now, starts=_STARTS)
        topics += [card for card in cards if card not in topics]
    except Exception as exc:
        logger.debug("UFC board skipped: %s", exc)
    _EVENTS.update(events_from_boards(boards, ufc_board, now=now))
    return topics
