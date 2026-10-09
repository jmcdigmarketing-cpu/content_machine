"""NFL team and player hints for sports search and domain detection."""

import re

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


# #1002: the full names a who's-who lookup and a scoreboard search need.
NFL_TEAM_NAMES = {
    "chargers": "Los Angeles Chargers", "chiefs": "Kansas City Chiefs",
    "eagles": "Philadelphia Eagles", "cowboys": "Dallas Cowboys",
    "49ers": "San Francisco 49ers", "niners": "San Francisco 49ers",
    "ravens": "Baltimore Ravens", "bills": "Buffalo Bills", "bengals": "Cincinnati Bengals",
    "dolphins": "Miami Dolphins", "jets": "New York Jets", "patriots": "New England Patriots",
    "steelers": "Pittsburgh Steelers", "browns": "Cleveland Browns", "texans": "Houston Texans",
    "colts": "Indianapolis Colts", "jaguars": "Jacksonville Jaguars",
    "titans": "Tennessee Titans", "broncos": "Denver Broncos", "raiders": "Las Vegas Raiders",
    "commanders": "Washington Commanders", "giants": "New York Giants",
    "packers": "Green Bay Packers", "vikings": "Minnesota Vikings", "bears": "Chicago Bears",
    "lions": "Detroit Lions", "saints": "New Orleans Saints", "falcons": "Atlanta Falcons",
    "panthers": "Carolina Panthers", "buccaneers": "Tampa Bay Buccaneers",
    "bucs": "Tampa Bay Buccaneers", "cardinals": "Arizona Cardinals",
    "rams": "Los Angeles Rams", "seahawks": "Seattle Seahawks",
}  # fmt: skip

# Words that make a nickname a team rather than a phone charger or a ram.
_SPORT_CUES = re.compile(
    r"\b(?:\d{1,2}-\d{1,2}|nfl|afc|nfc|super bowl|playoffs?|season|week \d+|qb|quarterback|"
    r"coach|draft|trade|roster|vs\.?|beat|game|win|wins|loss|losses|record|offense|defense|"
    r"touchdown|standings|division)\b",
    re.I,
)


def team_names_in(text: str) -> list[str]:
    """#1002: NFL teams a text names - lower-case too - as full names, in order.

    A nickname counts as a whole word, and only when something else in the text reads as
    football: a record ("0-4"), a league word, a second team, a known player. "best phone
    chargers 2026" names no team.
    """
    lower = (text or "").lower()
    found: list[str] = []
    for match in re.finditer(r"[a-z0-9]+", lower):
        full = NFL_TEAM_NAMES.get(match.group(0))
        if full and full not in found:
            found.append(full)
    if not found:
        return []
    players = any(re.search(rf"\b{re.escape(p)}\b", lower) for p in PLAYER_TO_TEAM)
    if len(found) > 1 or players or _SPORT_CUES.search(lower):
        return found
    return []


# ESPN's team abbreviations (#1003: the team page is /teams/<abbr>).
NFL_TEAM_ABBR = {
    "Los Angeles Chargers": "lac", "Kansas City Chiefs": "kc", "Philadelphia Eagles": "phi",
    "Dallas Cowboys": "dal", "San Francisco 49ers": "sf", "Baltimore Ravens": "bal",
    "Buffalo Bills": "buf", "Cincinnati Bengals": "cin", "Miami Dolphins": "mia",
    "New York Jets": "nyj", "New England Patriots": "ne", "Pittsburgh Steelers": "pit",
    "Cleveland Browns": "cle", "Houston Texans": "hou", "Indianapolis Colts": "ind",
    "Jacksonville Jaguars": "jax", "Tennessee Titans": "ten", "Denver Broncos": "den",
    "Las Vegas Raiders": "lv", "Washington Commanders": "wsh", "New York Giants": "nyg",
    "Green Bay Packers": "gb", "Minnesota Vikings": "min", "Chicago Bears": "chi",
    "Detroit Lions": "det", "New Orleans Saints": "no", "Atlanta Falcons": "atl",
    "Carolina Panthers": "car", "Tampa Bay Buccaneers": "tb", "Arizona Cardinals": "ari",
    "Los Angeles Rams": "lar", "Seattle Seahawks": "sea",
}  # fmt: skip
