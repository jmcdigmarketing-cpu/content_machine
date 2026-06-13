import os

import requests

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    STATUS_QUOTA,
    classify_exception,
    classify_http,
    make_signal,
)

ODDS_API_KEY = os.getenv("ODDS_API_KEY")


def get_odds_data(topic):
    if not ODDS_API_KEY:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set ODDS_API_KEY in .env",
        )

    try:
        url = f"https://api.the-odds-api.com/v4/sports/?apiKey={ODDS_API_KEY}"
        response = requests.get(url, timeout=10)

        remaining = response.headers.get("x-requests-remaining")
        if remaining is not None:
            try:
                if int(remaining) == 0:
                    return make_signal(
                        connected=False,
                        active=False,
                        status=STATUS_QUOTA,
                        status_detail="Odds API monthly quota exhausted",
                    )
            except ValueError:
                pass

        if response.status_code != 200:
            status, detail = classify_http(response.status_code, response.text)
            return make_signal(
                connected=False,
                active=False,
                status=status,
                status_detail=detail,
            )

        data = response.json()

        if not data:
            return make_signal(
                connected=True,
                active=False,
                score=0,
                confidence=0.6,
                status=STATUS_INACTIVE,
            )

        detail = None
        if remaining is not None:
            detail = f"{remaining} requests remaining this month"

        return make_signal(
            connected=True,
            active=True,
            score=50,
            confidence=0.6,
            data=data,
            status=STATUS_OK,
            status_detail=detail,
        )

    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
