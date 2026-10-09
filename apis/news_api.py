import os

import requests

from apis.schema_pins import drift, drift_signal
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)
from apis.topic_tokens import names_any, search_query, subject_markers, subject_terms


def _news_key() -> str:
    from config.settings import get_settings

    get_settings()
    return os.getenv("NEWS_API_KEY", "").strip()


def news_query(topic: str) -> tuple[str, list[str]]:
    """#1004: (NewsAPI query, subject markers). The topic's names, quoted and OR-ed - run 124
    sent the whole sentence and got iPhone and Uber stories - else its keywords."""
    terms = subject_terms(topic or "")[:2]
    if terms:
        return " OR ".join(f'"{t}"' for t in terms), subject_markers(terms)
    return search_query(topic or "", mode="keywords"), []


def get_news_score(query):
    if not _news_key():
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set NEWS_API_KEY in .env",
        )

    topic = query
    query, markers = news_query(topic)
    try:
        response = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": query, "apiKey": _news_key()},
            timeout=5,
        )

        if response.status_code != 200:
            status, detail = classify_http(response.status_code, response.text)
            return make_signal(
                connected=False,
                active=False,
                status=status,
                status_detail=detail,
            )

        data = response.json()
        if data.get("status") == "error":
            message = data.get("message", "NewsAPI error")
            code = (data.get("code") or "").lower()
            if "rate" in code or "limit" in message.lower():
                return make_signal(
                    connected=False,
                    active=False,
                    status="rate_limited",
                    status_detail=message,
                )
            if "apikey" in code or "authorization" in code:
                return make_signal(
                    connected=False,
                    active=False,
                    status="auth_error",
                    status_detail=message,
                )
            return make_signal(
                connected=False,
                active=False,
                status="error",
                status_detail=message,
            )

        drifted = drift("news", data)
        if drifted:
            return drift_signal(drifted)
        articles = data.get("articles", [])
        score = min(len(articles) * 10, 100)
        headlines = []
        off_topic = 0
        if markers:
            # #1004: a headline that names nothing the topic names is not about it.
            on = [
                a
                for a in articles
                if names_any(f"{a.get('title')} {a.get('description')}", markers)
            ]
            off_topic = len(articles) - len(on)
            articles = on
        for article in articles[:6]:
            title = (article.get("title") or "").strip()
            if not title or title == "[Removed]":
                continue
            headlines.append(
                {
                    "title": title,
                    "source": (article.get("source") or {}).get("name", ""),
                    "description": (article.get("description") or "")[:200],
                }
            )

        return make_signal(
            connected=True,
            active=len(articles) > 0,
            score=score,
            confidence=0.75,
            data={"headlines": headlines} if headlines else None,
            status=STATUS_OK if articles else STATUS_INACTIVE,
            status_detail=(
                (f"{off_topic} off-topic headline(s) dropped" if off_topic else None)
                if articles
                else f"No articles naming {query}"
                + (f" ({off_topic} off-topic dropped)" if off_topic else "")
            ),
        )

    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
