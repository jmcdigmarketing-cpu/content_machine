import os

import requests

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)


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

        score = min(len(results) * 15, 100)

        return make_signal(
            connected=True,
            active=len(results) > 0,
            score=score,
            confidence=0.85,
            data=results[:3],
            status=STATUS_OK if results else STATUS_INACTIVE,
        )

    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
