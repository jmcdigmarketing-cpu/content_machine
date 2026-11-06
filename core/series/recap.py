"""#1722 (B06.1, wave 147): a numbered UFC card's recap within 12 hours - every finish and what's
next, a long video drafted the night after the card, for your review (decision 84's long path).

The card and its results come from ESPN's keyless UFC board (`sports.espn`): its `calendar` names
the year's cards with their starts, and the board for the card's day lists every bout - the two
fighters, the winner, the round and the clock it ended on, and the rounds it was scheduled for.
Overnight runs at 05:00, about six hours after a Saturday main event ends, so the recap is drafted
from the results, not from memory; a card ESPN does not show as final yet waits for the next run.
`UFC_RECAP` (on by default; the suite pins it off).

Wave 152, from the same calendar: #1612 a numbered card's fight week - the six days before it
starts, its number and its main event's two names (`fight_week`) lead the night and arm the fast
lane's fight-week kind (#1874); #1892 its main event as a 6-8 minute match-up (`matchup_ideas`),
drafted for review two to five days before the card, gone once the card starts. `UFC_FIGHT_WEEK`
and `UFC_MATCHUP` (on by default; the suite pins both off).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from core.logging import get_logger

logger = get_logger("core.series.recap")

NUMBERED = re.compile(r"\bUFC \d{3}\b")
AFTER_HOURS = 3.0  # the card's start: the main event ends about five hours after it
WITHIN_HOURS = 36.0  # past this a recap is not news
_EASTERN = ZoneInfo("America/New_York")  # ESPN dates a card by its US evening


def recap_enabled() -> bool:
    return os.getenv("UFC_RECAP", "true").strip().lower() not in ("0", "false", "no", "off")


def finished_card(calendar: list[Any], *, now: datetime) -> tuple[str, datetime] | None:
    """The newest numbered card ("UFC 334: Gane vs. Hokit") that started between `WITHIN_HOURS`
    and `AFTER_HOURS` ago - a Fight Night is not one - with its start, or None."""
    found: list[tuple[datetime, str]] = []
    for entry in calendar or []:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip()
        try:
            start = datetime.fromisoformat(str(entry.get("startDate") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
        hours = (now - start).total_seconds() / 3600
        if NUMBERED.search(label) and AFTER_HOURS <= hours <= WITHIN_HOURS:
            found.append((start, label))
    if not found:
        return None
    start, label = max(found)
    return label, start


FIGHT_WEEK_DAYS = 6.0
MATCHUP_HOURS = (48.0, 120.0)  # two to five days before the card
_MAIN_EVENT = re.compile(r"^(UFC \d{3}):\s*(.+?)\s+vs\.?\s+(.+?)\s*$")


def _on(name: str) -> bool:
    return os.getenv(name, "true").strip().lower() not in ("0", "false", "no", "off")


def card_names(label: str) -> list[str]:
    """ "UFC 334: Gane vs. Hokit" -> ["UFC 334", "Gane", "Hokit"]; [] for a Fight Night."""
    found = _MAIN_EVENT.match(str(label or "").strip())
    return [found.group(1), found.group(2).strip(), found.group(3).strip()] if found else []


def _calendar(board: dict[str, Any] | None) -> list[Any]:
    leagues = (board or {}).get("leagues") or [{}]
    return (leagues[0] if isinstance(leagues[0], dict) else {}).get("calendar") or []


def coming_card(
    calendar: list[Any], *, now: datetime, low_hours: float, high_hours: float
) -> tuple[str, datetime] | None:
    """The soonest numbered card starting between `low_hours` and `high_hours` from now."""
    found: list[tuple[datetime, str]] = []
    for entry in calendar or []:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip()
        try:
            start = datetime.fromisoformat(str(entry.get("startDate") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
        hours = (start - now).total_seconds() / 3600
        if NUMBERED.search(label) and low_hours <= hours <= high_hours:
            found.append((start, label))
    if not found:
        return None
    start, label = min(found)
    return label, start


def _ufc_board() -> dict[str, Any]:
    from sports.espn import get_scoreboard

    return get_scoreboard("ufc") or {}


def fight_week(*, now: datetime | None = None, board: dict[str, Any] | None = None) -> list[str]:
    """#1612: the names of the numbered card starting within `FIGHT_WEEK_DAYS` - its number and
    its main event's two fighters - or []. Never raises."""
    if not _on("UFC_FIGHT_WEEK"):
        return []
    try:
        moment = now or datetime.now(timezone.utc)
        card = coming_card(_calendar(board if board is not None else _ufc_board()), now=moment,
                           low_hours=0.0, high_hours=FIGHT_WEEK_DAYS * 24)  # fmt: skip
        return card_names(card[0]) if card else []
    except Exception as exc:
        logger.debug("fight week unread: %s", exc)
        return []


def main_event_lines(
    label: str, start: datetime, *, fetch: Callable[..., dict[str, Any]] | None = None
) -> list[str]:
    """#1892: the main event as ESPN's board for the card's day lists it - the weight class, the
    rounds and each fighter's record. [] when the board does not list the card yet."""
    if fetch is None:
        from sports.espn import get_scoreboard

        fetch = get_scoreboard
    number = NUMBERED.search(label)
    key = number.group(0) if number else label
    days = dict.fromkeys([start.astimezone(_EASTERN).date(), start.astimezone(timezone.utc).date()])
    for day in days:
        try:
            board = fetch("ufc", dates=f"{day:%Y%m%d}")
        except Exception as exc:
            logger.debug("UFC board for %s unread: %s", day, exc)
            continue
        for event in (board or {}).get("events") or []:
            if not isinstance(event, dict) or key not in str(event.get("name") or ""):
                continue
            bouts = [b for b in event.get("competitions") or [] if isinstance(b, dict)]
            if not bouts:
                return []
            bout = bouts[-1]  # ESPN lists the main event last
            lines: list[str] = []
            weight = re.sub(
                r"^W ", "Women's ", str((bout.get("type") or {}).get("abbreviation") or "")
            )
            try:
                rounds = int(
                    ((bout.get("format") or {}).get("regulation") or {}).get("periods") or 0
                )
            except (TypeError, ValueError):
                rounds = 0
            spoken = {3: "three", 5: "five"}.get(rounds, str(rounds))
            if weight or rounds:
                lines.append(f"The main event is a {weight.lower() or 'scheduled'} bout"
                             + (f" over {spoken} rounds" if rounds else "") + " (ESPN's card).")  # fmt: skip
            for side in bout.get("competitors") or []:
                if not isinstance(side, dict):
                    continue
                record = next((str(r.get("summary") or "") for r in side.get("records") or []
                               if isinstance(r, dict) and r.get("summary")), "")  # fmt: skip
                if _name(side) and record:
                    lines.append(f"{_name(side)}'s record is {record} (ESPN).")
            return lines
    return []


def matchup_ideas(
    channel_id: str,
    *,
    now: datetime | None = None,
    board: dict[str, Any] | None = None,
    fetch: Callable[..., dict[str, Any]] | None = None,
    headlines: Callable[[str, dict[str, Any], datetime], list[dict[str, Any]]] | None = None,
    notes: list[str] | None = None,
) -> list[Any]:
    """#1892 (B12.21): a numbered card two to five days away, its main event as one long idea - "UFC
    334: Gane vs. Hokit - how they match up" - written from ESPN's card and the last three days'
    headlines naming either fighter, drafted for review, once. [] otherwise. Never raises."""
    if not _on("UFC_MATCHUP"):
        return []
    try:
        from core.batch_generation import series_drafted
        from core.best_bet import BestBetResult
        from core.series.countdown import feed_headlines, headline_facts

        moment = now or datetime.now(timezone.utc)
        low, high = MATCHUP_HOURS
        card = coming_card(_calendar(board if board is not None else _ufc_board()), now=moment,
                           low_hours=low, high_hours=high)  # fmt: skip
        names = card_names(card[0]) if card else []
        if card is None or not names:
            return []
        label, start = card
        topic = f"{label} - how they match up"
        if series_drafted(channel_id, topic):
            return []
        local = start.astimezone(_EASTERN)
        facts = [f"{label} is on {local:%A}, {local:%B} {local.day}, {local:%Y}; {names[1]} vs. "
                 f"{names[2]} is its main event (ESPN's calendar).",
                 *main_event_lines(label, start, fetch=fetch)]  # fmt: skip
        lines = (headlines or feed_headlines)(channel_id, {"domain": "ufc"}, moment)
        facts += headline_facts(names[1:], lines, now=moment, hours=72, limit=8)
        days = (start - moment).total_seconds() / 86400
        return [BestBetResult(
            topic=topic, domain="ufc", avg_engaged_rate=0.0, source="long", supporting_runs=0,
            facts=facts, draft_kind="long", deadline=start.isoformat(),
            rationale=f"series · {label} in {days:.1f} days - a 6-8 minute match-up, after your "
                      "review",
        )]  # fmt: skip
    except Exception as exc:
        logger.debug("UFC match-up skipped: %s", exc)
        return []


def _name(fighter: dict[str, Any] | None) -> str:
    return str(((fighter or {}).get("athlete") or {}).get("displayName") or "").strip()


def bout_lines(event: dict[str, Any]) -> list[str] | None:
    """The card's results as fact lines, the main event first - who beat whom, and how: a finish
    in round N at the clock, or the scorecards after the scheduled rounds. None while any bout is
    not final, or when the card lists none."""
    bouts = [b for b in event.get("competitions") or [] if isinstance(b, dict)]
    if not bouts:
        return None
    lines: list[str] = []
    for place, bout in enumerate(reversed(bouts)):
        status = bout.get("status") or {}
        if not (status.get("type") or {}).get("completed"):
            return None
        fighters = [f for f in bout.get("competitors") or [] if isinstance(f, dict)]
        winner = next((f for f in fighters if f.get("winner")), None)
        loser = next((f for f in fighters if f is not winner), None)
        weight = str((bout.get("type") or {}).get("abbreviation") or "").strip()
        weight = re.sub(r"^W ", "Women's ", weight)  # ESPN's "W Strawweight"
        label = ("Main event" if place == 0 else "Co-main event" if place == 1
                 else f"{weight} bout" if weight else "Bout")  # fmt: skip
        if place < 2 and weight:
            label += f" ({weight})"
        if winner is None:
            names = " and ".join(n for n in (_name(f) for f in fighters) if n)
            lines.append(f"{label}: {names} - no winner (a draw or a no contest).")
            continue
        try:
            rnd = int(status.get("period") or 0)
            rounds = int(((bout.get("format") or {}).get("regulation") or {}).get("periods") or 0)
        except (TypeError, ValueError):
            rnd, rounds = 0, 0
        rounds = rounds or (5 if place == 0 else 3)
        clock = str(status.get("displayClock") or "").strip()
        if rnd >= rounds and clock in ("5:00", "0:00", "", "-"):
            how = f"on the scorecards after {rounds} rounds"
        elif rnd:
            how = f"- a finish in round {rnd} at {clock}" if clock else f"- a finish in round {rnd}"
        else:
            how = ""
        lines.append(f"{label}: {_name(winner)} beat {_name(loser)} {how}".rstrip() + ".")
    return lines


def card_results(
    label: str, start: datetime, *, fetch: Callable[..., dict[str, Any]] | None = None
) -> list[str] | None:
    """`bout_lines` for the card, from ESPN's board for its day (US Eastern, then UTC)."""
    if fetch is None:
        from sports.espn import get_scoreboard

        fetch = get_scoreboard
    number = NUMBERED.search(label)
    key = number.group(0) if number else label
    days = dict.fromkeys([start.astimezone(_EASTERN).date(), start.astimezone(timezone.utc).date()])
    for day in days:
        try:
            board = fetch("ufc", dates=f"{day:%Y%m%d}")
        except Exception as exc:
            logger.debug("UFC board for %s unread: %s", day, exc)
            continue
        for event in (board or {}).get("events") or []:
            if isinstance(event, dict) and key in str(event.get("name") or ""):
                return bout_lines(event)
    return None


def recap_ideas(
    channel_id: str,
    *,
    now: datetime | None = None,
    board: dict[str, Any] | None = None,
    fetch: Callable[..., dict[str, Any]] | None = None,
    headlines: Callable[[str, dict[str, Any], datetime], list[dict[str, Any]]] | None = None,
    notes: list[str] | None = None,
) -> list[Any]:
    """The recap of a numbered card that ended overnight, as one long idea (source "long",
    drafted for review), once. Written from its results and the night's headlines naming it.
    [] when there is none, it is drafted, or ESPN does not show it final yet. Never raises."""
    if not recap_enabled():
        return []
    try:
        from core.batch_generation import series_drafted
        from core.best_bet import BestBetResult
        from core.series.countdown import feed_headlines, headline_facts

        moment = now or datetime.now(timezone.utc)
        if board is None:
            from sports.espn import get_scoreboard

            board = get_scoreboard("ufc")
        leagues = (board or {}).get("leagues") or [{}]
        calendar = (leagues[0] if isinstance(leagues[0], dict) else {}).get("calendar") or []
        card = finished_card(calendar, now=moment)
        if card is None:
            return []
        label, start = card
        number = NUMBERED.search(label)
        short = number.group(0) if number else label
        topic = f"{short} recap: every finish and what's next"
        if series_drafted(channel_id, topic):
            return []
        results = card_results(label, start, fetch=fetch)
        if not results:
            if notes is not None:
                notes.append(f'"{topic}" waits - ESPN does not show every {short} bout final yet')
            return []
        local = start.astimezone(_EASTERN)
        facts = [f"{label} was held on {local:%A}, {local:%B} {local.day}, {local:%Y} (ESPN's "
                 "results).", *results]  # fmt: skip
        lines = (headlines or feed_headlines)(channel_id, {"domain": "ufc"}, moment)
        facts += headline_facts([short], lines, now=moment, hours=18, limit=6)
        hours = max(1, round((moment - start).total_seconds() / 3600))
        return [BestBetResult(
            topic=topic, domain="ufc", avg_engaged_rate=0.0, source="long", supporting_runs=0,
            facts=facts, draft_kind="long",
            rationale=f"series · {label} started {hours} hours ago - a long recap, after your review",
        )]  # fmt: skip
    except Exception as exc:
        logger.debug("UFC recap skipped: %s", exc)
        return []
