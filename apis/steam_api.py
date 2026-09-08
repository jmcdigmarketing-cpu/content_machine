import os

import requests

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)


def steam_search_url(topic: str) -> str:
    from urllib.parse import quote_plus

    url = (
        "https://store.steampowered.com/api/storesearch/"
        f"?term={quote_plus(topic or '')}&l=english&cc=us"
    )
    key = os.getenv("STEAM_API_KEY", "").strip()
    if key:
        url += f"&key={quote_plus(key)}"
    return url


def get_steam_signal(topic):
    try:
        url = steam_search_url(topic)
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
        results = data.get("items", [])

        if not results:
            return make_signal(
                connected=True,
                active=False,
                score=0,
                confidence=0.6,
                status=STATUS_INACTIVE,
                status_detail="No Steam results for topic",
            )

        return make_signal(
            connected=True,
            active=True,
            score=min(len(results) * 10, 100),
            confidence=0.7,
            data=results[:5],
            status=STATUS_OK,
        )

    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
