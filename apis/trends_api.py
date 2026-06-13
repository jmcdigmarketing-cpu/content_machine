"""
Trend / interest signal — provider chain (no archived pytrends).

Chain: SerpApi Google Trends → Glimpse → Wikipedia pageviews (free, official).
"""

from __future__ import annotations

import os

import requests

from apis.signal_chain import ProviderFn, chain_signal
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    classify_exception,
    make_signal,
)
from apis.wikipedia_pageviews_api import get_wikipedia_pageviews_signal

_SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()
_GLIMPSE_KEY = os.getenv("GLIMPSE_API_KEY", "").strip()


def _trends_from_wikipedia(topic: str) -> dict:
    sig = get_wikipedia_pageviews_signal(topic)
    if not sig.get("active"):
        return sig
    out = dict(sig)
    data = dict(out.get("data") or {})
    data["trends_proxy"] = "wikipedia_pageviews"
    out["data"] = data
    detail = out.get("status_detail") or "Wikipedia pageview spike"
    out["status_detail"] = f"Trend proxy: {detail}"
    return out


def _trends_from_serpapi(topic: str) -> dict:
    if not _SERPAPI_KEY:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set SERPAPI_KEY for Google Trends",
        )
    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_trends",
                "q": topic,
                "api_key": _SERPAPI_KEY,
            },
            timeout=12,
        )
        if resp.status_code != 200:
            return make_signal(
                connected=False,
                active=False,
                status_detail=f"SerpApi HTTP {resp.status_code}",
            )
        payload = resp.json()
        interest = payload.get("interest_over_time") or {}
        timeline = interest.get("timeline_data") or []
        if not timeline:
            return make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="SerpApi: no trend timeline",
            )
        values = []
        for point in timeline[-14:]:
            for v in point.get("values") or []:
                raw = v.get("extracted_value") or v.get("value")
                if raw is not None:
                    try:
                        values.append(float(raw))
                    except (TypeError, ValueError):
                        pass
        if not values:
            return make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="SerpApi: empty values",
            )
        avg = sum(values) / len(values)
        score = min(100.0, avg * 10 if avg <= 10 else avg)
        return make_signal(
            connected=True,
            active=True,
            score=round(score, 1),
            confidence=0.85,
            status=STATUS_OK,
            status_detail="Google Trends via SerpApi",
            data={"provider": "serpapi", "samples": len(values)},
        )
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)


def _trends_from_glimpse(topic: str) -> dict:
    if not _GLIMPSE_KEY:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set GLIMPSE_API_KEY for Glimpse trends",
        )
    try:
        resp = requests.get(
            "https://api.glimpse.io/v1/trends",
            headers={"Authorization": f"Bearer {_GLIMPSE_KEY}"},
            params={"q": topic},
            timeout=12,
        )
        if resp.status_code != 200:
            return make_signal(
                connected=False,
                active=False,
                status_detail=f"Glimpse HTTP {resp.status_code}",
            )
        data = resp.json()
        growth = float(data.get("growth_rate") or data.get("growth") or 0)
        volume = float(data.get("volume") or data.get("search_volume") or 0)
        score = min(100.0, 30 + growth * 2 + min(volume / 1000, 40))
        active = score >= 20
        return make_signal(
            connected=True,
            active=active,
            score=round(score, 1),
            confidence=0.9,
            status=STATUS_OK if active else STATUS_INACTIVE,
            status_detail="Glimpse trend API",
            data=data,
        )
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)


def _trend_providers() -> list[tuple[str, ProviderFn]]:
    order = os.getenv("TRENDS_PROVIDER_ORDER", "serpapi,glimpse,wikipedia")
    registry = {
        "serpapi": _trends_from_serpapi,
        "glimpse": _trends_from_glimpse,
        "wikipedia": _trends_from_wikipedia,
    }
    providers: list[tuple[str, ProviderFn]] = []
    for name in order.split(","):
        key = name.strip().lower()
        if key in registry:
            providers.append((key, registry[key]))
    if not providers:
        providers.append(("wikipedia", _trends_from_wikipedia))
    return providers


def get_trend_score(topic: str) -> dict:
    return chain_signal(topic, _trend_providers(), min_score=15)
