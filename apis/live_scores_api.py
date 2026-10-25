import os
import re

from apis.nba_teams import is_nba_topic, team_display_matches, teams_in_topic
from apis.nfl_entities import NFL_TEAM_ABBR
from apis.nfl_entities import team_names_in as nfl_team_names_in
from apis.schema_pins import SchemaDrift, check, drift_signal
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    classify_exception,
    make_signal,
)
from core.logging import get_logger

logger = get_logger("apis.live_scores")

LIVE_SCORES_CACHE_TTL = 60 * 10  # 10 minutes — post-game results refresh quickly


def _parse_event(event):
    competition = (event.get("competitions") or [{}])[0]
    competitors = competition.get("competitors") or []
    status = event.get("status", {}).get("type", {})

    sides = {}
    leaders: dict[str, list[str]] = {}
    for comp in competitors:
        team = comp.get("team") or {}
        name = team.get("displayName") or team.get("shortDisplayName") or "Unknown"
        # #1575: ESPN's leaders per stat - the season's on a coming game, the game's once played.
        found = []
        for category in comp.get("leaders") or []:
            top = ((category or {}).get("leaders") or [{}])[0] or {}
            player = (top.get("athlete") or {}).get("displayName")
            value = top.get("displayValue")
            label = category.get("shortDisplayName") or category.get("abbreviation") or ""
            if player and value:
                found.append(f"{player} {value} {label}".strip())
        if found:
            leaders[name] = found[:3]
        sides[comp.get("homeAway", "away")] = {
            "team": name,
            "score": comp.get("score"),
            "winner": comp.get("winner") is True,
        }

    home = sides.get("home", {})
    away = sides.get("away", {})

    winner = None
    if home.get("winner"):
        winner = home.get("team")
    elif away.get("winner"):
        winner = away.get("team")

    return {
        "event_name": event.get("name") or event.get("shortName"),
        "date": str(event.get("date") or ""),  # #1363: when the whistle blew
        "leaders": leaders,  # #1575
        "status": status.get("description") or status.get("shortDetail") or status.get("name"),
        "completed": status.get("completed") is True,
        "home_team": home.get("team"),
        "away_team": away.get("team"),
        "home_score": home.get("score"),
        "away_score": away.get("score"),
        "winner": winner,
    }


def _lead_pair(names, topic):
    """#1560: the first two teams the topic names, in its order - the game it is about. Run 185's
    topic named four ("Chiefs edge Seahawks, Bengals over Ravens"); matching the board on all
    four tied two games at 2 and board order picked Bengals at Ravens."""
    lower = (topic or "").lower()

    def at(name):
        found = re.search(rf"\b{re.escape(str(name).lower())}\b", lower)
        return found.start() if found else len(lower)

    return sorted(dict.fromkeys(names), key=at)[:2]


def _match_score(event, topic_teams):
    if not topic_teams:
        return 1

    names = [event.get("home_team", ""), event.get("away_team", "")]
    hits = 0
    for nick in topic_teams:
        if any(team_display_matches(name, nick) for name in names):
            hits += 1
    return hits


def _team_line(payload, league):
    """Record, standing and next game from an ESPN team page (#1003). Raises SchemaDrift."""
    check("live_scores", payload)
    team = payload["team"]
    record = ""
    for item in (team.get("record") or {}).get("items") or []:
        if item.get("type") == "total" or not record:
            record = str(item.get("summary") or "")
            if item.get("type") == "total":
                break
    nxt = (team.get("nextEvent") or [{}])[0] or {}
    return {
        "team": team.get("displayName"),
        "record": record,
        "standing": str(team.get("standingSummary") or ""),
        "next_game": str(nxt.get("name") or ""),
        "next_date": str(nxt.get("date") or "")[:10],
        "league": league,
        "streak": _streak(payload),  # #1369
    }


def _streak(payload) -> str:
    """#1369: "W5" or "L2" from a team page's total record - ESPN signs it, -2 is two losses."""
    record = ((payload or {}).get("team") or {}).get("record") or {}
    for item in record.get("items") or []:
        if item.get("type") != "total":
            continue
        for stat in item.get("stats") or []:
            if stat.get("name") == "streak":
                value = int(stat.get("value") or 0)
                return f"W{value}" if value > 0 else f"L{-value}" if value < 0 else ""
    return ""


def _season_enabled() -> bool:
    """#1369: the schedule read, one request a team (`ESPN_SEASON_CONTEXT`, on; the suite's off)."""
    return os.getenv("ESPN_SEASON_CONTEXT", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def season_context(schedule, abbr, *, opponent="", last=5):
    """#1369: a team's last results this season, newest first ("W 22-6 vs LAC (Oct 18)"), and
    its meeting with `opponent` if they have played - so a preview's form claims have a fact."""
    from datetime import datetime as _dt

    def score(side):
        value = side.get("score")
        return str((value or {}).get("displayValue") if isinstance(value, dict) else value or "")

    results = []
    for event in (schedule or {}).get("events") or []:
        comp = (event.get("competitions") or [{}])[0]
        if not ((comp.get("status") or {}).get("type") or {}).get("completed"):
            continue
        sides = comp.get("competitors") or []
        ours = next(
            (
                c
                for c in sides
                if str((c.get("team") or {}).get("abbreviation") or "").upper() == abbr.upper()
            ),
            None,
        )
        theirs = next((c for c in sides if c is not ours), None)
        if ours is None or theirs is None:
            continue
        other = str((theirs.get("team") or {}).get("abbreviation") or "")
        raw = str(event.get("date") or "")
        try:
            day = _dt.fromisoformat(raw[:10])
            when = f"{day:%b} {day.day}"
        except ValueError:
            when = raw[:10]
        mark = "W" if ours.get("winner") else "L"
        where = "vs" if ours.get("homeAway") == "home" else "at"
        results.append(
            (raw, other, f"{mark} {score(ours)}-{score(theirs)} {where} {other} ({when})")
        )
    results.sort(key=lambda r: r[0], reverse=True)
    met = [text for _raw, other, text in results if opponent and other.upper() == opponent.upper()]
    return {"last": [text for _raw, _other, text in results[:last]], "met": met[0] if met else ""}


def _add_season(rows, abbrs, league):
    """#1369: each row's season so far. A bonus - the team pages are the facts. Fail-open."""
    if not _season_enabled():
        return
    from sports.espn import get_schedule

    for index, row in enumerate(rows):
        if index >= len(abbrs):
            break
        other = abbrs[1 - index] if len(abbrs) == 2 else ""
        try:
            row.update(
                season_context(get_schedule(league, abbrs[index]), abbrs[index], opponent=other)
            )
        except Exception as exc:
            logger.debug("season context skipped for %s %s: %s", league, abbrs[index], exc)


def _nfl_signal(topic, teams):
    """#1003: each named team's record, standing and next game, plus that week's game."""
    from sports.espn import get_scoreboard, get_team

    week_match = re.search(r"\bweek\s+(\d{1,2})\b", topic or "", re.I)
    week = int(week_match.group(1)) if week_match else None
    try:
        rows = [_team_line(get_team("nfl", NFL_TEAM_ABBR[t]), "nfl") for t in teams[:2]]
    except SchemaDrift as drift_exc:
        return drift_signal(str(drift_exc))
    _add_season(rows, [NFL_TEAM_ABBR[t] for t in teams[:2]], "nfl")  # #1369
    nicknames = _lead_pair([t.split()[-1].lower() for t in teams], topic)
    game = None
    try:
        events = (get_scoreboard("nfl", week=week) or {}).get("events") or []
        parsed = [_parse_event(ev) for ev in events]
        parsed.sort(key=lambda g: _match_score(g, nicknames), reverse=True)
        if parsed and _match_score(parsed[0], nicknames):
            game = parsed[0]
    except Exception as exc:  # the team pages are the facts; the board is a bonus
        logger.debug("NFL scoreboard skipped: %s", exc)
    rows = [r for r in rows if r.get("team")]
    if not rows:
        return make_signal(connected=True, active=False, status=STATUS_INACTIVE,
                           status_detail="ESPN NFL: no team page read")  # fmt: skip
    detail = "; ".join(f"{r['team']} {r['record']}".strip() for r in rows)
    return make_signal(
        connected=True,
        active=True,
        score=80 if game else 70,
        confidence=0.95,
        data={"teams": rows, "matched_game": game, "week": week, "source": "ESPN NFL"},
        status=STATUS_OK,
        status_detail=f"ESPN NFL: {detail}",
    )


def _injury_names(payload: dict) -> list[str]:
    names: list[str] = []
    for item in (payload or {}).get("injuries") or []:
        if not isinstance(item, dict):
            continue
        athlete = item.get("athlete") or {}
        name = athlete.get("displayName") if isinstance(athlete, dict) else ""
        if not name:
            continue
        status = str(item.get("status") or "").strip()
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        detail = str((details or {}).get("detail") or "").strip()
        bit = name
        extra = ", ".join(part for part in (status, detail) if part)
        if extra:
            bit += f" ({extra})"
        names.append(bit)
    return names


def _other_league_signal(topic: str, matches: list[tuple[str, str, str]]):
    """#1022: one league's named teams, each with its injury report."""
    from sports.espn import get_injuries, get_scoreboard, get_team

    league = matches[0][0]
    rows = []
    abbrs = []
    for _full, _league, abbr in [(m[1], m[0], m[2]) for m in matches if m[0] == league][:2]:
        try:
            row = _team_line(get_team(league, abbr), league)
        except SchemaDrift as drift_exc:
            return drift_signal(str(drift_exc))
        try:
            row["injuries"] = _injury_names(get_injuries(league, abbr))
        except Exception as exc:
            logger.warning("injury report unavailable for %s %s: %s", league, abbr, exc)
            row["injuries"] = []
        rows.append(row)
        abbrs.append(abbr)
    _add_season(rows, abbrs, league)  # #1369
    nicknames = [row["team"].split()[-1].lower() for row in rows if row.get("team")]
    game = None
    try:
        events = (get_scoreboard(league) or {}).get("events") or []
        parsed = [_parse_event(ev) for ev in events]
        parsed.sort(key=lambda g: _match_score(g, nicknames), reverse=True)
        if parsed and _match_score(parsed[0], nicknames):
            game = parsed[0]
    except Exception as exc:
        logger.debug("%s scoreboard skipped: %s", league, exc)
    rows = [r for r in rows if r.get("team")]
    if not rows:
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail=f"ESPN {league}: no team page read",
        )
    detail = "; ".join(f"{r['team']} {r['record']}".strip() for r in rows)
    return make_signal(
        connected=True,
        active=True,
        score=80 if game else 70,
        confidence=0.95,
        data={
            "teams": rows,
            "matched_game": game,
            "source": f"ESPN {league.upper()}",
        },
        status=STATUS_OK,
        status_detail=f"ESPN {league}: {detail}",
    )


def get_live_scores_signal(topic):
    """
    ESPN scoreboards - the NFL team pages and board (#1003), else the NBA board.
    """
    nfl_teams = nfl_team_names_in(topic or "")
    if nfl_teams:
        try:
            return _nfl_signal(topic, nfl_teams)
        except Exception as e:
            status, detail = classify_exception(e)
            return make_signal(connected=False, active=False, status=status,
                               status_detail=detail)  # fmt: skip
    from sports.teams import other_teams_in

    others = other_teams_in(topic or "")
    if others:
        try:
            return _other_league_signal(topic, others)
        except Exception as e:
            status, detail = classify_exception(e)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)
    if not is_nba_topic(topic):
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail="No NFL or NBA team in the topic",
        )

    try:
        from sports.espn import get_scoreboard

        board = get_scoreboard("nba")
        events = board.get("events") or []
        topic_teams = teams_in_topic(topic)

        parsed = [_parse_event(ev) for ev in events]
        if not parsed:
            return make_signal(
                connected=True,
                active=False,
                score=0,
                confidence=0.5,
                status=STATUS_INACTIVE,
                status_detail="No games on ESPN scoreboard",
            )

        lead = _lead_pair(topic_teams, topic)  # #1560
        parsed.sort(key=lambda g: _match_score(g, lead), reverse=True)
        best = parsed[0]
        match_hits = _match_score(best, lead)

        if topic_teams and match_hits == 0:
            return make_signal(
                connected=True,
                active=False,
                score=0,
                confidence=0.5,
                data={"games": parsed[:3], "note": "No scoreboard game matched topic teams"},
                status=STATUS_INACTIVE,
                status_detail="No game matched teams in topic",
            )

        score = 70
        if best.get("completed"):
            score += 20
        if topic_teams and match_hits >= 2:
            score += 10
        score = min(score, 100)

        return make_signal(
            connected=True,
            active=True,
            score=score,
            confidence=0.95,
            data={
                "matched_game": best,
                "other_games": parsed[1:3],
                "topic_teams": topic_teams,
                "source": "ESPN NBA scoreboard",
            },
            status=STATUS_OK,
            status_detail=f"{best.get('status')} — {best.get('event_name')}",
        )

    except Exception as e:
        status, detail = classify_exception(e)
        print(f"[Live Scores API Error] {detail}")
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )


def live_scores_cache_ttl():
    return LIVE_SCORES_CACHE_TTL
