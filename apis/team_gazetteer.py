"""Every team the channel's leagues field, as a city and a nickname (#1481, S19).

The title check knew NFL and NBA teams only, and read any three-word name minus its first word
as broken - so "Maple Leafs" or "Red Sox" would have failed it, and a hockey or baseball title
that lost its "New" ("York Rangers") passed. A team is broken when its city has two or more words
and the first is gone: "York Rangers", "Bay Lightning", "Louis Blues", "Ham United". A nickname
of two words ("Maple Leafs", "Golden Knights", "Trail Blazers") stands alone and is never broken.

NFL and NBA come from `apis.nfl_entities` and `apis.nba_teams`; NHL, MLB and the Premier League
are listed here. Data only - the title check and the caption and thumbnail cuts read it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Team:
    league: str
    city: str  # "" for a club with no city in its name ("Arsenal")
    nickname: str

    @property
    def full(self) -> str:
        return f"{self.city} {self.nickname}".strip()


# NFL and NBA nicknames of more than one word; every other nickname is the name's last word.
_TWO_WORD_NICKNAMES = frozenset({"Trail Blazers"})

NHL = (
    ("Anaheim", "Ducks"), ("Boston", "Bruins"), ("Buffalo", "Sabres"), ("Calgary", "Flames"),
    ("Carolina", "Hurricanes"), ("Chicago", "Blackhawks"), ("Colorado", "Avalanche"),
    ("Columbus", "Blue Jackets"), ("Dallas", "Stars"), ("Detroit", "Red Wings"),
    ("Edmonton", "Oilers"), ("Florida", "Panthers"), ("Los Angeles", "Kings"),
    ("Minnesota", "Wild"), ("Montreal", "Canadiens"), ("Nashville", "Predators"),
    ("New Jersey", "Devils"), ("New York", "Islanders"), ("New York", "Rangers"),
    ("Ottawa", "Senators"), ("Philadelphia", "Flyers"), ("Pittsburgh", "Penguins"),
    ("San Jose", "Sharks"), ("Seattle", "Kraken"), ("St. Louis", "Blues"),
    ("Tampa Bay", "Lightning"), ("Toronto", "Maple Leafs"), ("Utah", "Mammoth"),
    ("Vancouver", "Canucks"), ("Vegas", "Golden Knights"), ("Washington", "Capitals"),
    ("Winnipeg", "Jets"),
)  # fmt: skip
MLB = (
    ("Arizona", "Diamondbacks"), ("Atlanta", "Braves"), ("Baltimore", "Orioles"),
    ("Boston", "Red Sox"), ("Chicago", "Cubs"), ("Chicago", "White Sox"), ("Cincinnati", "Reds"),
    ("Cleveland", "Guardians"), ("Colorado", "Rockies"), ("Detroit", "Tigers"),
    ("Houston", "Astros"), ("Kansas City", "Royals"), ("Los Angeles", "Angels"),
    ("Los Angeles", "Dodgers"), ("Miami", "Marlins"), ("Milwaukee", "Brewers"),
    ("Minnesota", "Twins"), ("New York", "Mets"), ("New York", "Yankees"), ("", "Athletics"),
    ("Philadelphia", "Phillies"), ("Pittsburgh", "Pirates"), ("San Diego", "Padres"),
    ("San Francisco", "Giants"), ("Seattle", "Mariners"), ("St. Louis", "Cardinals"),
    ("Tampa Bay", "Rays"), ("Texas", "Rangers"), ("Toronto", "Blue Jays"),
    ("Washington", "Nationals"),
)  # fmt: skip
EPL = (
    ("", "Arsenal"), ("Aston", "Villa"), ("", "Bournemouth"), ("", "Brentford"),
    ("Brighton & Hove", "Albion"), ("", "Burnley"), ("", "Chelsea"), ("Crystal", "Palace"),
    ("", "Everton"), ("", "Fulham"), ("Leeds", "United"), ("", "Liverpool"),
    ("Manchester", "City"), ("Manchester", "United"), ("Newcastle", "United"),
    ("Nottingham", "Forest"), ("", "Sunderland"), ("Tottenham", "Hotspur"),
    ("West Ham", "United"), ("Wolverhampton", "Wanderers"),
)  # fmt: skip

# The ways a city's first word is written: "St. Louis", "St Louis", "Saint Louis".
_FIRST_WORD_VARIANTS = {"St.": ("St.", "St", "Saint")}
_CONNECTORS = frozenset({"&", "and"})


def _split(full: str) -> tuple[str, str]:
    for nickname in _TWO_WORD_NICKNAMES:
        if full.endswith(f" {nickname}"):
            return full[: -len(nickname) - 1], nickname
    city, _, nickname = full.rpartition(" ")
    return city, nickname


@lru_cache(maxsize=1)
def teams() -> tuple[Team, ...]:
    from apis.nba_teams import NBA_TEAM_NAMES
    from apis.nfl_entities import NFL_TEAM_NAMES

    out: list[Team] = []
    for league, names in (("NFL", NFL_TEAM_NAMES), ("NBA", NBA_TEAM_NAMES)):
        for full in sorted(set(names.values())):
            out.append(Team(league, *_split(full)))
    for league, rows in (("NHL", NHL), ("MLB", MLB), ("EPL", EPL)):
        out.extend(Team(league, city, nickname) for city, nickname in rows)
    return tuple(out)


@lru_cache(maxsize=1)
def broken_tails() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """(tail, full name, the prefixes that make the tail whole) for each team whose city has two
    or more words - ("York Rangers", "New York Rangers", ("New ",)), ("Hove Albion", "Brighton &
    Hove Albion", ("Brighton & ", "Brighton and "))."""
    out: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    for team in teams():
        words = team.city.split()
        if len(words) < 2:
            continue
        rest = words[1:]
        dropped = [words[0]]
        while rest and rest[0] in _CONNECTORS:
            dropped.append(rest.pop(0))
        tail = " ".join([*rest, team.nickname])
        firsts = _FIRST_WORD_VARIANTS.get(words[0], (words[0],))
        joins = (" & ", " and ") if len(dropped) > 1 else (" ",)
        prefixes = tuple(f"{first}{join}" for first in firsts for join in joins)
        out.setdefault(team.full, (tail, team.full, prefixes))
    return tuple(sorted(out.values(), key=lambda row: row[1]))


def _norm(word: str) -> str:
    return re.sub(r"(?:['’]s?)$", "", word.strip('.,:;!?"()').lower())


@lru_cache(maxsize=1)
def _name_words() -> tuple[tuple[str, ...], ...]:
    names: set[tuple[str, ...]] = set()
    for team in teams():
        if len(team.full.split()) < 2:
            continue
        words = team.full.split()
        for first in _FIRST_WORD_VARIANTS.get(words[0], (words[0],)):
            names.add(tuple(_norm(w) for w in [first, *words[1:]]))
    return tuple(sorted(names, key=len, reverse=True))


def team_spans(words: list[str]) -> list[tuple[int, int]]:
    """#1482/#1483: (start, end) word ranges where a team's full name of 2+ words is written -
    "New England Patriots" in "Why the New England Patriots can win" is (2, 5)."""
    normed = [_norm(w) for w in words]
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(normed):
        for name in _name_words():
            if tuple(normed[i : i + len(name)]) == name:
                spans.append((i, i + len(name)))
                i += len(name)
                break
        else:
            i += 1
    return spans
