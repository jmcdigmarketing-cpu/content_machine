"""Live web search — fresh, verified facts for topics past the LLM training cutoff.

Provider-agnostic: keyed Tavily (built for LLM grounding) > keyed Brave, or a keyless
DuckDuckGo backend for a truly-free ($0, no account) run. Selected via
`WEB_SEARCH_BACKEND` (unset = keyed-only; Free mode sets `duckduckgo`). The signal stays
inactive (no_key) until a provider is available, so it is safe to ship unset.

    TAVILY_API_KEY        — https://tavily.com (free tier ~1k searches/mo)
    BRAVE_SEARCH_API_KEY  — https://brave.com/search/api (free tier ~2k/mo)
    WEB_SEARCH_BACKEND=duckduckgo  — keyless (pip install ddgs); best-effort, $0

This is a *universal* signal (never domain-gated): it returns current facts and
headlines that ground the script against stale training memory — the core fix for
the recency gap on fast-moving sports/news topics.
"""

from __future__ import annotations

import os

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)

_TAVILY_URL = "https://api.tavily.com/search"
_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
_TTL = 90 * 60  # 90 min — breaking facts move fast
_MAX_RESULTS = 6


def _tavily_key() -> str:
    return os.getenv("TAVILY_API_KEY", "").strip()


def _brave_key() -> str:
    return (os.getenv("BRAVE_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY") or "").strip()


def _web_backend() -> str:
    """WEB_SEARCH_BACKEND=tavily|brave|duckduckgo|auto ('' = keyed-only, default)."""
    return os.getenv("WEB_SEARCH_BACKEND", "").strip().lower()


def _active_provider() -> str | None:
    """Pick the search provider. `duckduckgo` is keyless (always available); otherwise
    keyed Tavily > Brave; `auto` adds a keyless DuckDuckGo fallback when no key is set.
    Default (no backend, no key) stays None → the signal reports no_key, unchanged."""
    backend = _web_backend()
    if backend == "duckduckgo":
        return "duckduckgo"
    if _tavily_key():
        return "tavily"
    if _brave_key():
        return "brave"
    if backend == "auto":
        return "duckduckgo"  # keyless fallback, opt-in
    return None


def _tavily_search(topic: str) -> tuple[dict | None, tuple[str, str] | None]:
    """Returns (payload, error). payload = {answer, results:[{title,snippet,url}]}."""
    resp = requests.post(
        _TAVILY_URL,
        json={
            "api_key": _tavily_key(),
            "query": topic,
            "max_results": _MAX_RESULTS,
            "search_depth": "basic",
            "include_answer": True,
            "topic": "news",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        return None, classify_http(resp.status_code, resp.text)
    body = resp.json()
    results = [
        {
            "title": (r.get("title") or "").strip(),
            "snippet": (r.get("content") or "").strip(),
            "url": r.get("url") or "",
        }
        for r in (body.get("results") or [])
        if r.get("title") or r.get("content")
    ]
    return {"answer": (body.get("answer") or "").strip(), "results": results}, None


def _brave_search(topic: str) -> tuple[dict | None, tuple[str, str] | None]:
    resp = requests.get(
        _BRAVE_URL,
        headers={"X-Subscription-Token": _brave_key(), "Accept": "application/json"},
        params={"q": topic, "count": _MAX_RESULTS, "freshness": "pw"},
        timeout=15,
    )
    if resp.status_code != 200:
        return None, classify_http(resp.status_code, resp.text)
    body = resp.json()
    results = [
        {
            "title": (r.get("title") or "").strip(),
            "snippet": (r.get("description") or "").strip(),
            "url": r.get("url") or "",
        }
        for r in ((body.get("web") or {}).get("results") or [])
        if r.get("title") or r.get("description")
    ]
    return {"answer": "", "results": results}, None


def _duckduckgo_search(topic: str) -> tuple[dict | None, tuple[str, str] | None]:
    """Keyless web search via DuckDuckGo (ddgs) — no API key or account. Same payload
    shape as the keyed providers. Best-effort: DDG can throttle scrapers, so any failure
    returns an error tuple and the signal fails open (never raises)."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # older package name
        except ImportError:
            return None, (STATUS_NO_KEY, "pip install ddgs for keyless web search")
    try:
        with DDGS() as ddgs:
            hits = list(ddgs.text(topic, max_results=_MAX_RESULTS))
    except Exception as exc:
        return None, classify_exception(exc)
    results = [
        {
            "title": (h.get("title") or "").strip(),
            "snippet": (h.get("body") or "").strip(),
            "url": h.get("href") or "",
        }
        for h in hits
        if h.get("title") or h.get("body")
    ]
    return {"answer": "", "results": results}, None


_SEARCHERS = {
    "tavily": _tavily_search,
    "brave": _brave_search,
    "duckduckgo": _duckduckgo_search,
}


def get_web_search_signal(topic: str) -> dict:
    provider = _active_provider()
    if not provider:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set TAVILY_API_KEY or BRAVE_SEARCH_API_KEY for live web facts",
        )

    cache_key = build_key("web_search", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        payload, error = _SEARCHERS[provider](topic)
        if error is not None:
            status, detail = error
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        results = (payload or {}).get("results") or []
        answer = (payload or {}).get("answer") or ""
        if not results and not answer:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail=f"Web search ({provider}): no results",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        score = min(50 + len(results) * 7, 95)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.8,
            status=STATUS_OK,
            status_detail=f"Web search ({provider}): {len(results)} result(s)",
            data={"provider": provider, "answer": answer, "results": results},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
