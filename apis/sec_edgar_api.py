"""SEC EDGAR full-text search — official filings (free, no key)."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)

_BASE = "https://efts.sec.gov/LATEST/search-index"
_TTL = 6 * 60 * 60
_UA = {
    "User-Agent": os.getenv(
        "SEC_EDGAR_USER_AGENT",
        "ContentMachine/1.0 (research@contentmachine.local)",
    ),
    "Accept": "application/json",
}


def _search_query(topic: str) -> str:
    text = re.sub(r"\b(20\d{2}|stock|stocks|earnings|analysis)\b", "", topic, flags=re.I)
    words = re.findall(r"[A-Za-z][a-z]+", text)
    if len(words) >= 2:
        return " ".join(words[:4])
    return topic.strip()[:48]


def get_sec_edgar_signal(topic: str) -> dict:
    cache_key = build_key("sec_edgar", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    query = _search_query(topic)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=90)
    try:
        resp = requests.get(
            _BASE,
            params={
                "q": f'"{query}"',
                "dateRange": "custom",
                "startdt": start.isoformat(),
                "enddt": end.isoformat(),
            },
            headers=_UA,
            timeout=14,
        )
        if resp.status_code != 200:
            status, detail = classify_http(resp.status_code, resp.text)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        payload = resp.json()
        hits = (payload.get("hits") or {}).get("hits") or []
        if not hits:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="SEC EDGAR: no recent filings match",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        filings = []
        for hit in hits[:6]:
            src = hit.get("_source") or {}
            filings.append(
                {
                    "form": src.get("form", ""),
                    "filed": src.get("file_date", ""),
                    "entity": (src.get("display_names") or [""])[0],
                }
            )
        score = min(40 + len(filings) * 10, 90)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.88,
            status=STATUS_OK,
            status_detail=f"SEC EDGAR: {len(filings)} recent filings",
            data={"filings": filings},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
