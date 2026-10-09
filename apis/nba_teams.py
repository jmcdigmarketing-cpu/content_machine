"""Shared NBA team nickname detection for sports + live score signals."""

import re

TEAM_NICKNAMES = (
    "knicks",
    "lakers",
    "celtics",
    "warriors",
    "nets",
    "bucks",
    "heat",
    "suns",
    "nuggets",
    "clippers",
    "mavericks",
    "spurs",
    "rockets",
    "bulls",
    "sixers",
    "76ers",
    "raptors",
    "hawks",
    "hornets",
    "magic",
    "pacers",
    "pistons",
    "cavaliers",
    "cavs",
    "grizzlies",
    "pelicans",
    "thunder",
    "timberwolves",
    "wolves",
    "blazers",
    "kings",
    "jazz",
    "wizards",
)

NBA_TOPIC_HINTS = (
    "nba",
    "finals",
    "playoff",
    "playoffs",
    "basketball",
    "game 1",
    "game 2",
    "game 3",
    "game 4",
    "game 5",
    "game 6",
    "game 7",
    "semifinal",
    "conference",
)


def teams_in_topic(topic):
    lower = topic.lower()
    return [nick for nick in TEAM_NICKNAMES if nick in lower]


def is_nba_topic(topic):
    lower = topic.lower()
    if any(hint in lower for hint in NBA_TOPIC_HINTS):
        return True
    return bool(teams_in_topic(topic))


def team_display_matches(display_name, nick):
    lower = display_name.lower()
    if nick in lower:
        return True
    return bool(nick in ("sixers", "76ers") and ("76ers" in lower or "sixers" in lower))


# #1002: full names for the who's-who lookup.
NBA_TEAM_NAMES = {
    "knicks": "New York Knicks", "lakers": "Los Angeles Lakers", "celtics": "Boston Celtics",
    "warriors": "Golden State Warriors", "nets": "Brooklyn Nets", "bucks": "Milwaukee Bucks",
    "heat": "Miami Heat", "suns": "Phoenix Suns", "nuggets": "Denver Nuggets",
    "clippers": "Los Angeles Clippers", "mavericks": "Dallas Mavericks",
    "spurs": "San Antonio Spurs", "rockets": "Houston Rockets", "bulls": "Chicago Bulls",
    "sixers": "Philadelphia 76ers", "76ers": "Philadelphia 76ers",
    "raptors": "Toronto Raptors", "hawks": "Atlanta Hawks", "hornets": "Charlotte Hornets",
    "magic": "Orlando Magic", "pacers": "Indiana Pacers", "pistons": "Detroit Pistons",
    "cavaliers": "Cleveland Cavaliers", "cavs": "Cleveland Cavaliers",
    "grizzlies": "Memphis Grizzlies", "pelicans": "New Orleans Pelicans",
    "thunder": "Oklahoma City Thunder", "timberwolves": "Minnesota Timberwolves",
    "wolves": "Minnesota Timberwolves", "blazers": "Portland Trail Blazers",
    "kings": "Sacramento Kings", "jazz": "Utah Jazz", "wizards": "Washington Wizards",
}  # fmt: skip

_SPORT_CUES = re.compile(
    r"\b(?:\d{1,3}-\d{1,3}|nba|playoffs?|finals|season|game \d|coach|draft|trade|roster|"
    r"vs\.?|beat|win|wins|loss|losses|record|standings|conference|basketball)\b",
    re.I,
)


def team_names_in(text: str) -> list[str]:
    """#1002: NBA teams a text names, lower-case too, as full names - only when the text
    reads as basketball ("the heat wave in phoenix" names no team)."""
    lower = (text or "").lower()
    found: list[str] = []
    for match in re.finditer(r"[a-z0-9]+", lower):
        full = NBA_TEAM_NAMES.get(match.group(0))
        if full and full not in found:
            found.append(full)
    if found and (len(found) > 1 or _SPORT_CUES.search(lower)):
        return found
    return []
