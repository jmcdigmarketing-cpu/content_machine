"""Pinned response shapes: a renamed field is an error, not "no results" (#385, #906).

Each JSON signal reads its payload through `.get(..., [])` defaults, so a provider that
renames `results` or an item's `name` used to make the signal report a healthy "no
match" (`STATUS_INACTIVE`) forever - thinner facts, no incident, nothing in `ops
reliability`. A pin names what a parser actually reads:

    signal -> Pin(container path, item keys, optional)

- `container` is a dotted path (`data.Page.media`), or None for a top-level list;
- an item key may list alternatives (`title|name`: TMDB movies vs shows);
- `optional=True` means an absent path is an empty answer (Brave leaves out `web` when
  there are no web results), so only a missing leaf under a present parent is drift.

`drift(signal, payload)` compares a 200's body with the pin. It is deliberately narrow:

- an empty answer is never drift (`{"results": []}`, TheSportsDB's `{"teams": null}`,
  GraphQL's `{"data": null, "errors": [...]}`);
- a path that is absent is drift, and so is the wrong top-level type;
- a single object where a list is expected is one item (Last.fm's one-match shape);
- an item key is drift only when *no* item carries it (one sparse item is data, not a
  renamed field).

A drifted signal returns `drift_signal(...)`: connected, inactive, `STATUS_UPSTREAM`,
"schema drift: ...". That status is a live failure (the stale-cache fallback may serve
the last good answer) and is not in the session breaker's trip set, so a drift never
disables a signal for the run. A parser that reads the body inside a helper raises
`SchemaDrift` through `check()` and its signal turns that into `drift_signal`.

The recorded payloads the pins are tested against live in
`tests/fixtures/signal_payloads/` (#626); a fixture without a pin fails the suite, and
`ops record-payloads` (#905) refreshes them from the live APIs.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from apis.signal_contract import STATUS_UPSTREAM, make_signal


class Pin(NamedTuple):
    container: str | None
    keys: tuple[str, ...]
    optional: bool = False


PINS: dict[str, Pin] = {
    "rawg": Pin("results", ("name",)),  # api.rawg.io/api/games
    "news": Pin("articles", ("title",)),  # newsapi.org/v2/everything
    "fred": Pin("seriess", ("title",)),  # api.stlouisfed.org/fred/series/search
    "coingecko": Pin("coins", ("name",)),  # api.coingecko.com/api/v3/search
    "web_search": Pin("results", ("title", "content")),  # api.tavily.com/search
    "web_search_brave": Pin("web.results", ("title", "description"), optional=True),
    "sports": Pin("teams", ("strTeam",)),  # thesportsdb.com searchteams.php
    "odds": Pin(None, ("key",)),  # api.the-odds-api.com/v4/sports
    "twitch": Pin("data", ("id", "name")),  # api.twitch.tv/helix/games/top
    # #906
    "tmdb": Pin("results", ("title|name",)),  # api.themoviedb.org/3/search/multi
    "tvmaze": Pin(None, ("show",)),  # api.tvmaze.com/search/shows
    "jikan": Pin("data", ("title",)),  # api.jikan.moe/v4/anime
    "anilist": Pin("data.Page.media", ("title",)),  # graphql.anilist.co
    "finnhub": Pin(None, ("headline",)),  # finnhub.io/api/v1/news, /company-news
    "balldontlie": Pin("data", ()),  # api.balldontlie.io players / stats / fighters
    "wikipedia": Pin("items", ("views",)),  # wikimedia.org pageviews per-article
    "musicbrainz": Pin("releases", ("title",)),  # musicbrainz.org/ws/2/release
    "lastfm": Pin("results.trackmatches.track", ("name",)),  # ws.audioscrobbler.com
    # #1003: the NFL team page (record, standing, next game); the NBA board is unpinned.
    "live_scores": Pin("team", ("displayName",)),  # site.api.espn.com .../nfl/teams/<abbr>
}


class SchemaDrift(Exception):
    """A 200 whose body no longer matches its pin; the message is `drift()`'s text."""


def _walk(payload: Any, path: str) -> tuple[bool, Any]:
    """(found, value) for a dotted path. A None on the way is found-and-empty."""
    node = payload
    for part in path.split("."):
        if node is None:
            return True, None
        if not isinstance(node, dict) or part not in node:
            return False, None
        node = node[part]
    return True, node


def _has(item: dict, key: str) -> bool:
    return any(alt in item for alt in key.split("|"))


def drift(signal: str, payload: Any) -> str | None:
    """What no longer matches the pin, or None (also None for an unpinned signal)."""
    pin = PINS.get(signal)
    if pin is None:
        return None
    if pin.container is None:
        if not isinstance(payload, list):
            return f"expected a list, got {type(payload).__name__}"
        items = payload
        where = "[]"
    else:
        if not isinstance(payload, dict):
            return f"expected an object, got {type(payload).__name__}"
        found, value = _walk(payload, pin.container)
        if not found:
            if pin.optional and _walk(payload, pin.container.split(".")[0])[0] is False:
                return None  # the optional parent is absent: an empty answer
            return f"missing `{pin.container}`"
        if value is None:
            return None
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            return f"`{pin.container}` is {type(value).__name__}, not a list"
        items = value
        where = f"{pin.container}[]"
    if not items:
        return None
    dicts = [item for item in items if isinstance(item, dict)]
    if not dicts:
        return f"`{where}` items are not objects"
    for key in pin.keys:
        if not any(_has(item, key) for item in dicts):
            return f"`{where}` items lack `{key}`"
    return None


def check(signal: str, payload: Any) -> None:
    """Raise `SchemaDrift` when `payload` drifted from the pin (for parsers in helpers)."""
    found = drift(signal, payload)
    if found:
        raise SchemaDrift(found)


def drift_signal(detail: str) -> dict[str, Any]:
    """The `make_signal` a drifted 200 returns."""
    return make_signal(
        connected=True,
        active=False,
        status=STATUS_UPSTREAM,
        status_detail=f"schema drift: {detail}",
    )
