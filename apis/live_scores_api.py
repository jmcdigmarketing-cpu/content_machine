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
    for comp in competitors:
        team = comp.get("team") or {}
        name = team.get("displayName") or team.get("shortDisplayName") or "Unknown"
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
        "status": status.get("description") or status.get("shortDetail") or status.get("name"),
        "completed": status.get("completed") is True,
        "home_team": home.get("team"),
        "away_team": away.get("team"),
        "home_score": home.get("score"),
        "away_score": away.get("score"),
        "winner": winner,
    }


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
    }


def _nfl_signal(topic, teams):
    """#1003: each named team's record, standing and next game, plus that week's game."""
    from sports.espn import get_scoreboard, get_team

    week_match = re.search(r"\bweek\s+(\d{1,2})\b", topic or "", re.I)
    week = int(week_match.group(1)) if week_match else None
    try:
        rows = [_team_line(get_team("nfl", NFL_TEAM_ABBR[t]), "nfl") for t in teams[:2]]
    except SchemaDrift as drift_exc:
        return drift_signal(str(drift_exc))
    nicknames = [t.split()[-1].lower() for t in teams]
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

        parsed.sort(key=lambda g: _match_score(g, topic_teams), reverse=True)
        best = parsed[0]
        match_hits = _match_score(best, topic_teams)

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
