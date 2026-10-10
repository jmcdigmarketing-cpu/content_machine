"""Nicknames for the leagues ESPN covers beyond the NFL and NBA (#1022)."""

from __future__ import annotations

import re

# nickname -> (display name, ESPN abbreviation). Longest nicknames match first.
TEAMS: dict[str, dict[str, tuple[str, str]]] = {
    "nhl": {
        "maple leafs": ("Toronto Maple Leafs", "tor"),
        "bruins": ("Boston Bruins", "bos"),
        "canadiens": ("Montreal Canadiens", "mtl"),
        "blackhawks": ("Chicago Blackhawks", "chi"),
        "red wings": ("Detroit Red Wings", "det"),
        "canucks": ("Vancouver Canucks", "van"),
        "oilers": ("Edmonton Oilers", "edm"),
    },
    "mlb": {
        "yankees": ("New York Yankees", "nyy"),
        "dodgers": ("Los Angeles Dodgers", "lad"),
        "red sox": ("Boston Red Sox", "bos"),
        "cubs": ("Chicago Cubs", "chc"),
        "mets": ("New York Mets", "nym"),
    },
    "college-football": {
        "crimson tide": ("Alabama Crimson Tide", "ala"),
        "buckeyes": ("Ohio State Buckeyes", "osu"),
        "wolverines": ("Michigan Wolverines", "mich"),
        "bulldogs": ("Georgia Bulldogs", "ga"),
    },
    "soccer": {
        "manchester city": ("Manchester City", "382"),
        "liverpool": ("Liverpool", "364"),
        "arsenal": ("Arsenal", "359"),
        "chelsea": ("Chelsea", "363"),
    },
}


def other_teams_in(text: str) -> list[tuple[str, str, str]]:
    """(league, display name, abbreviation) for NHL, MLB, college football and soccer."""
    lower = (text or "").lower()
    found: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    phrases = [
        (nick, league, full, abbr)
        for league, table in TEAMS.items()
        for nick, (full, abbr) in table.items()
    ]
    for nick, league, full, abbr in sorted(phrases, key=lambda row: -len(row[0])):
        if full in seen:
            continue
        if re.search(rf"\b{re.escape(nick)}\b", lower):
            found.append((league, full, abbr))
            seen.add(full)
    return found
