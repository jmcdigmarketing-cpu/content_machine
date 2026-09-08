from apis.nba_teams import is_nba_topic, team_display_matches, teams_in_topic
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    classify_exception,
    make_signal,
)

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


def get_live_scores_signal(topic):
    """
    ESPN NBA scoreboard — final/live box scores for games tied to the topic.
    """
    if not is_nba_topic(topic):
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail="NBA scoreboard only (NFL live scores not wired yet)",
        )

    try:
        from sports.espn import get_scoreboard

        board = get_scoreboard()
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
