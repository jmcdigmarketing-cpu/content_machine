import os
import re

import requests

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)
from apis.topic_tokens import FUNCTION_WORDS

# Words that carry no game-identity signal when matching a result to a topic.
# FUNCTION_WORDS added after run 98: "what", "this", "does", "mean" in a typed
# question made "What's This?" (2 of 2 tokens) and "What does it mean!?" count as
# matches for a Premier League topic.
_RELEVANCE_STOP = {"new", "update", "vs"} | set(FUNCTION_WORDS)
_ROMAN = re.compile(r"^[ivxlcdm]+$")


def _sig_tokens(text: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-z0-9]+", (text or "").lower())
        if t not in _RELEVANCE_STOP and len(t) > 1
    ]


def _acronym(name: str) -> str:
    """First letters of a game's significant words ('Grand Theft Auto' -> 'gta')."""
    words = [w for w in re.findall(r"[A-Za-z]+", name or "") if w.lower() not in _RELEVANCE_STOP]
    return "".join(w[0].lower() for w in words if not _ROMAN.match(w.lower()))


def _is_relevant(game_name: str, topic_tokens: set[str]) -> bool:
    """
    True if a RAWG result actually matches the topic, not just a fuzzy neighbor.

    RAWG's search is loose ("Marvel Rivals" returns "Need for Speed Rivals"), so
    keep a result only when most of its name appears in the topic OR its acronym
    matches a topic token (so abbreviations like GTA -> Grand Theft Auto survive).
    """
    name_tokens = _sig_tokens(game_name)
    if not name_tokens:
        return False
    overlap = sum(1 for t in name_tokens if t in topic_tokens)
    if overlap / len(name_tokens) > 0.5:
        return True
    acr = _acronym(game_name)
    return len(acr) >= 2 and acr in topic_tokens


# Candidate 324. `_is_relevant` measures how much of a GAME NAME appears in the topic,
# which is necessary but not sufficient: it has no notion of whether the game is the
# SUBJECT of the story. Live-run 71 covered a 2026 GTA 6 leak under the angle
# "...Wolverine Rage...", and the gate correctly passed three games by its own rule —
# "Wolverine: Adamantium Rage" (1994) scores 2 of 3 name tokens = 0.667 > 0.5,
# "X-Men: Wolverine's Rage" (2001) likewise, and bare "Wolverine" (1991) scores 1.0.
# All three were injected as facts, and the authenticity gate counted them toward its
# "18 verified fact(s)" substance evidence.
#
# Release era is what separates them: a game from 1991 is not evidence about a 2026
# news story. Fail-open — a missing or unparseable date keeps the result.
_DEFAULT_MAX_AGE_YEARS = 15
# Topics that are *about* older games; the age rule must not fire on these.
_RETRO_CUE = re.compile(
    r"\b(retro|classic|classics|nostalgia|anniversary|remaster(?:ed|s)?|remake|"
    r"throwback|history|greatest\s+of\s+all\s+time|revisit(?:ed|ing)?|"
    r"decades?\s+(?:later|old)|all\s+time)\b",
    re.IGNORECASE,
)
_YEAR = re.compile(r"\b(19[5-9]\d|20\d\d)\b")


def _max_age_years() -> int:
    raw = os.getenv("RAWG_MAX_AGE_YEARS", "").strip()
    if not raw:
        return _DEFAULT_MAX_AGE_YEARS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_MAX_AGE_YEARS
    return value if value > 0 else 0  # 0 disables the rule


def _released_year(game: dict) -> int | None:
    match = _YEAR.match(str(game.get("released") or "").strip()[:4])
    return int(match.group(1)) if match else None


def _topic_is_retro(topic: str) -> bool:
    """True when the topic is itself about older games, so age must not disqualify."""
    text = topic or ""
    if _RETRO_CUE.search(text):
        return True
    from datetime import datetime, timezone

    current = datetime.now(timezone.utc).year
    # An explicit old year in the topic ("the 1998 original") signals retro intent.
    return any(int(y) < current - _DEFAULT_MAX_AGE_YEARS for y in _YEAR.findall(text))


def _is_current_era(game: dict, topic: str, *, now_year: int | None = None) -> bool:
    """False when a matched game is too old to be evidence about this topic (324)."""
    max_age = _max_age_years()
    if not max_age or _topic_is_retro(topic):
        return True
    year = _released_year(game)
    if year is None:
        return True  # fail-open: no date is not evidence of staleness
    if now_year is None:
        from datetime import datetime, timezone

        now_year = datetime.now(timezone.utc).year
    return (now_year - year) <= max_age


def _rawg_key() -> str:
    from config.settings import get_settings

    get_settings()
    return os.getenv("RAWG_API_KEY", "").strip()


def get_rawg_signal(topic):
    if not _rawg_key():
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set RAWG_API_KEY in .env",
        )

    try:
        url = f"https://api.rawg.io/api/games?search={topic}&key={_rawg_key()}"
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
        results = data.get("results", [])

        # Drop fuzzy neighbors RAWG returns for loose name matches, so only the
        # game(s) the topic is actually about get injected as facts.
        topic_tokens = set(_sig_tokens(topic))
        relevant = [
            g
            for g in results
            if _is_relevant(g.get("name", ""), topic_tokens) and _is_current_era(g, topic)
        ]

        score = min(len(relevant) * 15, 100)

        return make_signal(
            connected=True,
            active=len(relevant) > 0,
            score=score,
            confidence=0.85,
            data=relevant[:3],
            status=STATUS_OK if relevant else STATUS_INACTIVE,
        )

    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
