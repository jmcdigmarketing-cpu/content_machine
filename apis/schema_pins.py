"""Pinned response shapes: a renamed field is an error, not "no results" (#385).

Each JSON signal reads its payload through `.get(..., [])` defaults, so a provider that
renames `results` or an item's `name` used to make the signal report a healthy "no
match" (`STATUS_INACTIVE`) forever - thinner facts, no incident, nothing in `ops
reliability`. A pin names what a parser actually reads:

    signal -> (container key, or None for a top-level list; item keys every parse needs)

`drift(signal, payload)` compares a 200's body with the pin. It is deliberately narrow:

- an empty answer is never drift (`{"results": []}`, TheSportsDB's `{"teams": null}`);
- a container key that is absent is drift, and so is the wrong top-level type;
- an item key is drift only when *no* item carries it (one sparse item is data, not a
  renamed field).

A drifted signal returns `drift_signal(...)`: connected, inactive, `STATUS_UPSTREAM`,
"schema drift: ...". That status is a live failure (the stale-cache fallback may serve
the last good answer) and is not in the session breaker's trip set, so a drift never
disables a signal for the run. The recorded payloads the pins are tested against live
in `tests/fixtures/signal_payloads/` (#626); a fixture without a pin fails the suite.
"""

from __future__ import annotations

from typing import Any

from apis.signal_contract import STATUS_UPSTREAM, make_signal

PINS: dict[str, tuple[str | None, tuple[str, ...]]] = {
    "rawg": ("results", ("name",)),  # api.rawg.io/api/games
    "news": ("articles", ("title",)),  # newsapi.org/v2/everything
    "fred": ("seriess", ("title",)),  # api.stlouisfed.org/fred/series/search
    "coingecko": ("coins", ("name",)),  # api.coingecko.com/api/v3/search
    "web_search": ("results", ("title", "content")),  # api.tavily.com/search
    "sports": ("teams", ("strTeam",)),  # thesportsdb.com searchteams.php
    "odds": (None, ("key",)),  # api.the-odds-api.com/v4/sports
    "twitch": ("data", ("id", "name")),  # api.twitch.tv/helix/games/top
}


def drift(signal: str, payload: Any) -> str | None:
    """What no longer matches the pin, or None (also None for an unpinned signal)."""
    pin = PINS.get(signal)
    if pin is None:
        return None
    container, item_keys = pin
    if container is None:
        if not isinstance(payload, list):
            return f"expected a list, got {type(payload).__name__}"
        items = payload
        where = "[]"
    else:
        if not isinstance(payload, dict):
            return f"expected an object, got {type(payload).__name__}"
        if container not in payload:
            return f"missing `{container}`"
        value = payload[container]
        if value is None:
            return None
        if not isinstance(value, list):
            return f"`{container}` is {type(value).__name__}, not a list"
        items = value
        where = f"{container}[]"
    dicts = [item for item in items if isinstance(item, dict)]
    if not items:
        return None
    if not dicts:
        return f"`{where}` items are not objects"
    for key in item_keys:
        if not any(key in item for item in dicts):
            return f"`{where}` items lack `{key}`"
    return None


def drift_signal(detail: str) -> dict[str, Any]:
    """The `make_signal` a drifted 200 returns."""
    return make_signal(
        connected=True,
        active=False,
        status=STATUS_UPSTREAM,
        status_detail=f"schema drift: {detail}",
    )
