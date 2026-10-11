import re

import requests

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    classify_exception,
    classify_http,
    make_signal,
)

# Google Suggest 400s on the run 76 thesis (punctuation + length). Keep a
# searchable seed, not the four-question paste.
_SUGGEST_MAX = 80


def _suggest_query(topic: str) -> str:
    flat = re.sub(r"[!?]+", " ", topic or "")
    flat = re.sub(r"\s+", " ", flat).strip()
    if len(flat) <= _SUGGEST_MAX:
        return flat
    return flat[:_SUGGEST_MAX].rsplit(" ", 1)[0].strip()


def get_autocomplete_data(topic):
    """
    Uses Google Suggest unofficial endpoint for keyword expansion.
    """

    try:
        url = "https://suggestqueries.google.com/complete/search"
        query = _suggest_query(topic)
        params = {
            "client": "firefox",
            "q": query,
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 400:
            return make_signal(
                connected=False,
                active=False,
                status=STATUS_UNAVAILABLE,
                status_detail="autocomplete skipped: query rejected (400)",
            )

        if response.status_code != 200:
            status, detail = classify_http(response.status_code, response.text)
            return make_signal(
                connected=False,
                active=False,
                status=status,
                status_detail=detail,
            )

        suggestions = response.json()[1]

        score = min(len(suggestions) * 10, 100)

        return make_signal(
            connected=True,
            active=len(suggestions) > 0,
            score=score,
            confidence=0.7,
            data=suggestions[:5],
            status=STATUS_OK if suggestions else STATUS_INACTIVE,
        )

    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )


def youtube_suggestions(phrase: str) -> list[str] | None:
    """What people type into YouTube after `phrase` (#1050), or None when it cannot be read.

    Not a discovery signal: one lookup per run, at title time, on the title's subject. The
    signal above asks Google about the whole topic sentence and mostly comes back empty.
    Never raises.
    """
    query = _suggest_query(phrase)
    if not query:
        return None
    try:
        response = requests.get(
            "https://suggestqueries.google.com/complete/search",
            params={"client": "firefox", "ds": "yt", "q": query},
            timeout=6,
        )
        if response.status_code != 200:
            return None
        found = response.json()[1]
    except Exception:
        return None
    return [str(item).strip().lower() for item in found if str(item).strip()][:10]
