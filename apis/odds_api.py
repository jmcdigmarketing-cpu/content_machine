import os

import requests

from apis.schema_pins import drift, drift_signal
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

# The topic's domain -> the sport keys that are that domain. Soccer is matched per
# league below, because a club story names no league and a league story names one.
_DOMAIN_KEYS = {
    "nfl": ("americanfootball_nfl",),
    "nba": ("basketball_nba",),
    "ufc": ("mma_mixed_martial_arts",),
}


def topic_sports(topic, sports):
    """#897: the sports in the API's list that this topic is about ([] = none).

    The signal used to return the whole list for every topic and score it 50, so an
    NFL story, a Premier League story and a club fine all got the same bump.
    """
    from apis.topic_scorer import infer_topic_domain
    from apis.topic_tokens import contains_phrase, content_tokens

    domain = infer_topic_domain(topic)
    live = [s for s in sports or [] if isinstance(s, dict) and s.get("active", True)]
    if domain in _DOMAIN_KEYS:
        return [s for s in live if s.get("key") in _DOMAIN_KEYS[domain]]
    if domain != "soccer":
        return []
    words = set(content_tokens(topic, min_len=3))
    out = []
    for sport in live:
        if sport.get("group") != "Soccer":
            continue
        described = set(content_tokens(str(sport.get("description") or ""), min_len=3))
        if contains_phrase(topic, str(sport.get("title") or "")) or len(words & described) >= 2:
            out.append(sport)
    return out


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

        body = response.json()
        drifted = drift("odds", body)
        if drifted:
            return drift_signal(drifted)
        data = topic_sports(topic, body)

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
