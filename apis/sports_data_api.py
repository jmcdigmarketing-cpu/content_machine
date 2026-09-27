# apis/sports_data_api.py

import os
import re

import requests

from apis.nba_teams import teams_in_topic as nba_teams_in_topic
from apis.nfl_entities import team_search_term as nfl_team_search_term
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)
from apis.topic_tokens import contains_phrase

SPORTSDB_API_KEY = os.getenv("SPORTSDB_API_KEY")


def _resolved_team(topic):
    """The team the NFL/NBA resolvers found (a player -> team, a nickname), or ""."""
    nfl_term = nfl_team_search_term(topic)
    if nfl_term:
        return nfl_term
    found = nba_teams_in_topic(topic)
    return found[0] if found else ""


def _team_search_term(topic):
    resolved = _resolved_team(topic)
    if resolved:
        return resolved

    match = re.search(r"\b([A-Z][a-zA-Z]+)\b", topic)
    if match:
        return match.group(1)

    words = topic.lower().split()
    if len(words) >= 2:
        return words[-1]

    return topic.split()[0] if topic.split() else topic


def _team_names(team):
    names = [team.get("strTeam") or "", team.get("strTeamShort") or ""]
    names += [a.strip() for a in str(team.get("strAlternate") or "").split(",")]
    return [n for n in names if n]


def _team_in_topic(team, topic, resolved):
    """#896: the topic names this team, or the resolvers already mapped it to it.

    The search term can be the topic's first capitalised word ("Premier"), so the API
    answers with whatever club carries that word - a cricket club for a football story.
    """
    names = _team_names(team)
    if any(contains_phrase(topic, name) for name in names):
        return True
    return bool(resolved) and any(contains_phrase(name, resolved) for name in names)


def get_sports_data(topic):
    if not SPORTSDB_API_KEY:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set SPORTSDB_API_KEY in .env",
        )

    try:
        search_term = _team_search_term(topic)
        url = (
            f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_API_KEY}"
            f"/searchteams.php?t={search_term}"
        )
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            status, detail = classify_http(response.status_code, response.text)
            return make_signal(
                connected=False,
                active=False,
                status=status,
                status_detail=detail,
            )

        data = response.json()

        if not data.get("teams"):
            return make_signal(
                connected=True,
                active=False,
                score=0,
                confidence=0.5,
                status=STATUS_INACTIVE,
                status_detail=f"No teams found for '{search_term}'",
            )

        resolved = _resolved_team(topic)
        teams = [
            t for t in data["teams"] if isinstance(t, dict) and _team_in_topic(t, topic, resolved)
        ]
        if not teams:
            return make_signal(
                connected=True,
                active=False,
                score=0,
                confidence=0.5,
                status=STATUS_INACTIVE,
                status_detail=f"'{search_term}' matched no team named in the topic",
            )

        score = min(len(teams) * 25, 100)

        return make_signal(
            connected=True,
            active=True,
            score=score,
            confidence=0.7,
            data=teams,
            status=STATUS_OK,
        )

    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
