"""Shared NBA team nickname detection for sports + live score signals."""

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
