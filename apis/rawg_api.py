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

# Words that carry no game-identity signal when matching a result to a topic.
_RELEVANCE_STOP = {"the", "of", "for", "a", "an", "and", "new", "update", "vs", "is", "to"}
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
        relevant = [g for g in results if _is_relevant(g.get("name", ""), topic_tokens)]

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
