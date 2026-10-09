"""ESPN's keyless site API - scoreboards and team pages (#1003: the league is a parameter).

Run 118 asked "why can we not pull more up to date data?": this module pointed at the NBA
scoreboard only, so an NFL recap had no result to stand on. Network calls live here; the
`live_scores` signal parses them and never raises.
"""

import requests

_SITE = "https://site.api.espn.com/apis/site/v2/sports"
LEAGUES = {"nba": "basketball/nba", "nfl": "football/nfl"}

# Kept for callers that imported the old constant.
BASE_URL = f"{_SITE}/{LEAGUES['nba']}"


def _get(url: str, params: dict | None = None) -> dict:
    response = requests.get(url, params=params, timeout=10)
    if response.status_code != 200:
        raise Exception(f"ESPN fetch failed ({response.status_code}): {url}")
    return response.json()


def get_scoreboard(league: str = "nba", *, week: int | None = None) -> dict:
    """The league's current board, or that week's ("week N" topics, NFL)."""
    return _get(f"{_SITE}/{LEAGUES[league]}/scoreboard", {"week": week} if week else None)


def get_team(league: str, team: str) -> dict:
    """A team page: record, standing and next game. `team` is ESPN's abbreviation."""
    return _get(f"{_SITE}/{LEAGUES[league]}/teams/{team.lower()}")
