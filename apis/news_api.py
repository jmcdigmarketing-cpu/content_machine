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


def _news_key() -> str:
    from config.settings import get_settings

    get_settings()
    return os.getenv("NEWS_API_KEY", "").strip()


def get_news_score(query):
    if not _news_key():
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set NEWS_API_KEY in .env",
        )

    try:
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={_news_key()}"
        response = requests.get(url, timeout=5)

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

        articles = data.get("articles", [])
        score = min(len(articles) * 10, 100)
        headlines = []
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
            status_detail=None if articles else "No articles for query",
        )

    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
