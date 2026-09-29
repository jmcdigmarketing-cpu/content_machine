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
from typing import Any

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.schema_pins import drift
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    STATUS_UPSTREAM,
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


def _tavily_search(
    topic: str, days: int | None = None
) -> tuple[dict | None, tuple[str, str] | None]:
    """Returns (payload, error). payload = {answer, results:[{title,snippet,url}]}."""
    request: dict[str, Any] = {
        "api_key": _tavily_key(),
        "query": topic,
        "max_results": _MAX_RESULTS,
        "search_depth": "basic",
        "include_answer": True,
        "topic": "news",
    }
    if days:
        request["days"] = int(days)  # #899: news from the last N days only
    resp = requests.post(_TAVILY_URL, json=request, timeout=15)
    if resp.status_code != 200:
        return None, classify_http(resp.status_code, resp.text)
    body = resp.json()
    drifted = drift("web_search", body)  # #385: a renamed field is an error, not "no results"
    if drifted:
        return None, (STATUS_UPSTREAM, f"schema drift: {drifted}")
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


def _brave_search(
    topic: str, days: int | None = None
) -> tuple[dict | None, tuple[str, str] | None]:
    freshness = "pd" if days and days <= 1 else "pw" if not days or days <= 7 else "pm"
    resp = requests.get(
        _BRAVE_URL,
        headers={"X-Subscription-Token": _brave_key(), "Accept": "application/json"},
        params={"q": topic, "count": _MAX_RESULTS, "freshness": freshness},
        timeout=15,
    )
    if resp.status_code != 200:
        return None, classify_http(resp.status_code, resp.text)
    body = resp.json()
    drifted = drift("web_search_brave", body)  # #906
    if drifted:
        return None, (STATUS_UPSTREAM, f"schema drift: {drifted}")
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


def _duckduckgo_search(
    topic: str, days: int | None = None
) -> tuple[dict | None, tuple[str, str] | None]:
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
            if days:
                # #899: the news index with a time limit, not the evergreen web index.
                limit = "d" if days <= 1 else "w" if days <= 7 else "m"
                hits = list(ddgs.news(topic, timelimit=limit, max_results=_MAX_RESULTS))
            else:
                hits = list(ddgs.text(topic, max_results=_MAX_RESULTS))
    except Exception as exc:
        return None, classify_exception(exc)
    results = [
        {
            "title": (h.get("title") or "").strip(),
            "snippet": (h.get("body") or "").strip(),
            "url": h.get("href") or h.get("url") or "",
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


def _fallback_enabled() -> bool:
    """#589: `WEB_SEARCH_FALLBACK` (default on). The suite pins it off - no network."""
    return os.getenv("WEB_SEARCH_FALLBACK", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _ddgs_available() -> bool:
    import importlib.util

    return any(importlib.util.find_spec(m) is not None for m in ("ddgs", "duckduckgo_search"))


def _provider_chain() -> list[str]:
    """#589: the providers to ask in order - the active one, the other keyed one, then
    keyless DuckDuckGo when `ddgs` is installed (operator's choice, wave 46).

    Free mode (`WEB_SEARCH_BACKEND=duckduckgo`) never falls back to a paid key, and no
    provider at all stays `[]` (the signal reports no_key, unchanged).
    """
    first = _active_provider()
    if not first:
        return []
    if first == "duckduckgo" or not _fallback_enabled():
        return [first]
    chain = [first]
    for name, has_key in (("tavily", _tavily_key()), ("brave", _brave_key())):
        if has_key and name not in chain:
            chain.append(name)
    if _ddgs_available():
        chain.append("duckduckgo")
    return chain


def _search_chain(
    query: str, days: int | None = None
) -> tuple[dict | None, str, list[str], tuple[str, str] | None, bool]:
    """(payload, provider that answered, what the others said, first error, any empty).

    The first provider with a result or an answer wins. An empty answer or an error moves
    on to the next; both are named ("tavily empty", "brave rate_limited").
    """
    tried: list[str] = []
    first_error: tuple[str, str] | None = None
    any_empty = False
    for provider in _provider_chain():
        try:
            payload, error = (
                _SEARCHERS[provider](query, days) if days else _SEARCHERS[provider](query)
            )
        except Exception as exc:
            payload, error = None, classify_exception(exc)
        if error is not None:
            first_error = first_error or error
            tried.append(f"{provider} {error[0]}")
            continue
        if (payload or {}).get("results") or (payload or {}).get("answer"):
            return payload, provider, tried, first_error, any_empty
        any_empty = True
        tried.append(f"{provider} empty")
    return None, "", tried, first_error, any_empty


def search_recent(query: str, *, days: int = 7) -> list[dict]:
    """Results for `query` from the last `days` days, or []. Never raises (#899).

    Event research searches the event's *name* ("UFC Freedom 250") with a recency
    window; the signal above searches the whole typed topic with none. Same provider
    chain (#589) and payload shape; its own cache key.
    """
    if not _provider_chain() or not (query or "").strip():
        return []
    cache_key = build_key("web_search_recent", f"{days}d:{query}")
    cached = get_cached(cache_key)
    if isinstance(cached, list):
        return cached
    payload, _provider, _tried, error, _empty = _search_chain(query, days)
    if payload is None and error is not None:
        return []
    results = [r for r in (payload or {}).get("results") or [] if isinstance(r, dict)]
    set_cache(cache_key, results, ttl_seconds=_TTL)
    return results


def get_web_search_signal(topic: str) -> dict:
    chain = _provider_chain()
    if not chain:
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
        payload, provider, tried, error, any_empty = _search_chain(topic)
        after = f" (after {', '.join(tried)})" if tried else ""
        if payload is None and error is not None and not any_empty:
            status, detail = error
            if len(tried) > 1:
                detail = f"{detail} [{' -> '.join(tried)}]"
            return make_signal(connected=False, active=False, status=status, status_detail=detail)
        if payload is None:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail=f"Web search ({', '.join(chain)}): no results{after if error else ''}",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        results = payload.get("results") or []
        answer = payload.get("answer") or ""
        via = f"{' -> '.join([*tried, provider])}: " if tried else ""
        score = min(50 + len(results) * 7, 95)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.8,
            status=STATUS_OK,
            status_detail=f"Web search ({provider}): {via}{len(results)} result(s)",
            data={"provider": provider, "answer": answer, "results": results, "tried": tried},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
