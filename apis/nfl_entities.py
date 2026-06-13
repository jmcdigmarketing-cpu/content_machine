"""NFL team and player hints for sports search and domain detection."""

NFL_TEAM_NICKNAMES = (
    "chargers",
    "chiefs",
    "eagles",
    "cowboys",
    "49ers",
    "niners",
    "ravens",
    "bills",
    "bengals",
    "dolphins",
    "jets",
    "patriots",
    "steelers",
    "browns",
    "texans",
    "colts",
    "jaguars",
    "titans",
    "broncos",
    "raiders",
    "commanders",
    "giants",
    "packers",
    "vikings",
    "bears",
    "lions",
    "saints",
    "falcons",
    "panthers",
    "buccaneers",
    "bucs",
    "cardinals",
    "rams",
    "seahawks",
)

PLAYER_TO_TEAM = {
    "justin herbert": "chargers",
    "herbert": "chargers",
    "patrick mahomes": "chiefs",
    "mahomes": "chiefs",
    "josh allen": "bills",
    "lamar jackson": "ravens",
    "joe burrow": "bengals",
    "trevor lawrence": "jaguars",
    "caleb williams": "bears",
    "jayden daniels": "commanders",
    "c.j. stroud": "texans",
    "stroud": "texans",
}

NFL_TOPIC_HINTS = (
    "nfl",
    "super bowl",
    "quarterback",
    "qb",
    "touchdown",
    "afc",
    "nfc",
    "wild card",
    "playoff",
)


def teams_in_topic(topic: str):
    lower = topic.lower()
    return [t for t in NFL_TEAM_NICKNAMES if t in lower]


def team_search_term(topic: str) -> str:
    lower = topic.lower()

    for player, team in sorted(PLAYER_TO_TEAM.items(), key=lambda x: -len(x[0])):
        if player in lower:
            return team

    found = teams_in_topic(topic)
    if found:
        return found[0]

    return ""


def is_nfl_topic(topic: str) -> bool:
    lower = topic.lower()
    if any(h in lower for h in NFL_TOPIC_HINTS):
        return True
    if team_search_term(topic):
        return True
    return any(p in lower for p in PLAYER_TO_TEAM)
