"""
Wikipedia pageviews — leading public-interest indicator (free, no API key).

Uses Wikimedia REST metrics API. Often leads search/trends for breaking topics.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    classify_exception,
    make_signal,
)

_WIKI_ENABLED = os.getenv("WIKIPEDIA_PAGEVIEWS_ENABLED", "true").lower() not in (
    "0",
    "false",
    "no",
)
_BASE = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user"
)
_TTL = 12 * 60 * 60


def _article_candidates(topic: str) -> list[str]:
    """Guess Wikipedia article titles from a topic string."""
    cleaned = re.sub(r"[^\w\s]", " ", topic)
    words = [w for w in cleaned.split() if len(w) > 2]
    if not words:
        return []
    candidates = []
    # Full title case underscore
    title = "_".join(w.capitalize() for w in words[:6])
    candidates.append(title)
    if len(words) >= 2:
        candidates.append("_".join(w.capitalize() for w in words[:3]))
    candidates.append(words[0].capitalize())
    # Dedupe preserving order
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _fetch_pageviews(article: str) -> dict | None:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=14)
    url = f"{_BASE}/{article}/daily/" f"{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}"
    resp = requests.get(
        url,
        timeout=8,
        headers={"User-Agent": "ContentMachine/1.0 (research signal)"},
    )
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        resp.raise_for_status()
    data = resp.json()
    items = data.get("items") or []
    if not items:
        return None
    views = [int(it.get("views", 0)) for it in items if it.get("views") is not None]
    if not views:
        return None
    return {"article": article, "views": views, "daily": items}


def _spike_score(views: list[int]) -> tuple[float, str]:
    """Compare recent 3-day avg vs prior 7-day avg."""
    if len(views) < 5:
        avg = sum(views) / len(views)
        return min(100.0, avg / 500.0 * 100), "limited history"

    recent = views[-3:]
    prior = views[-10:-3] if len(views) >= 10 else views[:-3]
    if not prior:
        prior = views[:3]

    r_avg = sum(recent) / len(recent)
    p_avg = sum(prior) / len(prior) or 1.0
    ratio = r_avg / p_avg

    if ratio >= 2.0:
        score = min(100.0, 55 + (ratio - 2) * 15)
        detail = f"pageview spike {ratio:.1f}× vs prior week"
    elif ratio >= 1.3:
        score = min(85.0, 35 + (ratio - 1.3) * 40)
        detail = f"pageviews rising {ratio:.1f}×"
    elif ratio <= 0.7:
        score = max(10.0, 25 * ratio)
        detail = f"pageviews cooling {ratio:.1f}×"
    else:
        score = min(60.0, r_avg / 800.0 * 100)
        detail = "stable pageview level"

    return round(score, 1), detail


def get_wikipedia_pageviews_signal(topic: str) -> dict:
    if not _WIKI_ENABLED:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_UNAVAILABLE,
            status_detail="WIKIPEDIA_PAGEVIEWS_ENABLED=false",
        )

    cache_key = build_key("wikipedia", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        best = None
        best_score = 0.0
        best_detail = ""
        best_article = ""

        for article in _article_candidates(topic):
            payload = _fetch_pageviews(article)
            if not payload:
                continue
            score, detail = _spike_score(payload["views"])
            if score > best_score:
                best_score = score
                best_detail = detail
                best_article = article
                best = payload

        if not best:
            result = make_signal(
                connected=True,
                active=False,
                score=0,
                confidence=0.5,
                status=STATUS_INACTIVE,
                status_detail="No Wikipedia article match for topic",
            )
            set_cache(cache_key, result, ttl_seconds=_TTL)
            return result

        active = best_score >= 20
        result = make_signal(
            connected=True,
            active=active,
            score=best_score,
            confidence=0.75 if active else 0.4,
            status=STATUS_OK if active else STATUS_INACTIVE,
            status_detail=f"{best_article}: {best_detail}",
            data={"article": best_article, "views_recent": best["views"][-3:]},
        )
        set_cache(cache_key, result, ttl_seconds=_TTL)
        return result

    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
