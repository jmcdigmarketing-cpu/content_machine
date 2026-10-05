"""Event research on a miss: look for the event before stopping the run (#899).

Wave 43's recency guard (`core/event_coverage`, #895) notices when no verified fact names
what the topic names - "UFC Freedom 250" with only generic UFC headlines - and stops
before the voice. The operator asked the next question: shouldn't it pull more data
first? Nothing did. The web search signal searches the whole typed topic with no recency
window, and auto-research (#848) only reads the pages that search already returned.

This runs only on a miss, and only for the event's name (the `search_query(mode=
"entity")` name the guard checked):

1. **Wikipedia** - search, then the intro of the article whose title names the event.
   Recent events get an article within hours; its intro is written to be read cold.
2. **Google News RSS** - headlines from the last seven days that name the event. Keyless.
3. **The configured web provider** - `apis.web_search_api.search_recent(name, days=7)`,
   the results that name the event and the top two pages read (`auto_research._read`).

Lines are kept only when they are about the event: a headline or snippet must name it
(`event_coverage.covered`), an article or page must be titled for it. They ride as an
`event_research` signal at web tier (score 0 - the composite never moves), and coverage
is checked again. Bounded by `EVENT_RESEARCH_DEADLINE_S`, cached per name, never raises.
`EVENT_RESEARCH_ENABLED=false` turns it off (the suite pins it off: no network in tests).
"""

from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any
from xml.etree import ElementTree

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import STATUS_OK, make_signal
from core.logging import get_logger

logger = get_logger("core.event_research")

SIGNAL_NAME = "event_research"
_CACHE_TTL = 3 * 60 * 60
_WIKI_API = "https://en.wikipedia.org/w/api.php"
_NEWS_RSS = "https://news.google.com/rss/search"
_HEADERS = {"User-Agent": "ContentMachine/1.0 (event research)"}
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def research_enabled() -> bool:
    from core.providers import flag_enabled

    return flag_enabled("EVENT_RESEARCH_ENABLED", default=True)


def _env_num(name: str, default: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(os.getenv(name, str(default)) or default)))
    except ValueError:
        return default


def precheck(
    topic: str, signals: dict[str, Any] | None, key_facts: list[str] | None
) -> dict[str, Any] | None:
    """`event_coverage.coverage` over the signals' verified facts, before any script."""
    from core.content_engine import _split_facts_block
    from core.event_coverage import coverage
    from core.signal_facts import format_signal_facts

    verified, _context = _split_facts_block(format_signal_facts(dict(signals or {})))
    return coverage(topic, verified, list(key_facts or []))


def _names_it(name: str, text: str) -> bool:
    from core.event_coverage import covered

    return covered(name, [text])


def _wikipedia(name: str, _exclude: set[str]) -> list[str]:
    resp = requests.get(
        _WIKI_API,
        params={"action": "query", "list": "search", "srsearch": name, "srlimit": "3",
                "format": "json"},
        headers=_HEADERS,
        timeout=8,
    )  # fmt: skip
    if resp.status_code != 200:
        return []
    hits = ((resp.json() or {}).get("query") or {}).get("search") or []
    title = next(
        (str(h.get("title")) for h in hits if h.get("title") and _names_it(name, str(h["title"]))),
        "",
    )
    if not title:
        return []
    resp = requests.get(
        _WIKI_API,
        params={"action": "query", "prop": "extracts", "exintro": "1", "explaintext": "1",
                "redirects": "1", "titles": title, "format": "json"},
        headers=_HEADERS,
        timeout=8,
    )  # fmt: skip
    if resp.status_code != 200:
        return []
    pages = ((resp.json() or {}).get("query") or {}).get("pages") or {}
    extract = " ".join(str(p.get("extract") or "") for p in pages.values() if isinstance(p, dict))
    return [s.strip() for s in _SENTENCE.split(extract) if len(s.strip()) > 20]


def _google_news(name: str, _exclude: set[str]) -> list[str]:
    return google_news_headlines(name)


def google_news_headlines(name: str, *, window: str = "7d") -> list[str]:
    """Google News headlines naming `name` from the last `window` ("2d", "7d"), each with
    its day. Keyless; raises on a network error (callers decide what an outage means)."""
    resp = requests.get(
        _NEWS_RSS,
        params={"q": f'"{name}" when:{window}', "hl": "en-US", "gl": "US", "ceid": "US:en"},
        headers=_HEADERS,
        timeout=8,
    )
    if resp.status_code != 200:
        return []
    root = ElementTree.fromstring(resp.text)
    lines: list[str] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title or not _names_it(name, title):
            continue
        day = " ".join((item.findtext("pubDate") or "").split()[1:4])
        lines.append(f"{title} ({day})" if day else title)
    return lines


def _web(name: str, exclude: set[str]) -> list[str]:
    from apis.web_search_api import search_recent
    from core.auto_research import _read
    from core.facts.selection import flag_off_topic

    lines: list[str] = []
    pages = 0
    for result in search_recent(name, days=7):
        title = str(result.get("title") or "").strip()
        snippet = str(result.get("snippet") or "").strip()
        if not _names_it(name, f"{title} {snippet}"):
            continue
        lines.append(f"{title}: {snippet}" if snippet else title)
        url = str(result.get("url") or "")
        if url.startswith("http") and url not in exclude and pages < 2:
            pages += 1
            body = _read(url)
            off = set(flag_off_topic(body, reference=name, corpus=f"{title} {snippet}"))
            lines.extend(line for line in body if line not in off)
    return lines


_SOURCES = (("Wikipedia", _wikipedia), ("Google News", _google_news), ("Web search", _web))


def research_event(name: str, *, exclude_urls: list[str] | None = None) -> dict[str, Any]:
    """`{lines, sources, seconds}` for the event's name. Never raises; cached per name."""
    key = build_key(SIGNAL_NAME, name)
    cached = get_cached(key)
    if isinstance(cached, dict) and "lines" in cached:
        return cached
    exclude = set(exclude_urls or [])
    cap = int(_env_num("EVENT_RESEARCH_MAX_LINES", 12, 1, 60))
    started = time.monotonic()
    found: dict[str, list[str]] = {}
    executor = ThreadPoolExecutor(max_workers=len(_SOURCES))
    futures = {executor.submit(fn, name, exclude): label for label, fn in _SOURCES}
    timed_out = False
    try:
        for future in as_completed(
            futures, timeout=_env_num("EVENT_RESEARCH_DEADLINE_S", 20, 0.1, 120)
        ):
            label = futures[future]
            try:
                found[label] = [str(x) for x in future.result() or [] if str(x).strip()]
            except Exception as exc:
                logger.debug("event research: %s failed for %r: %s", label, name, exc)
    except FuturesTimeout:
        timed_out = True
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    lines: list[str] = []
    sources: list[str] = []
    for label, _fn in _SOURCES:  # source order, not completion order
        took = False
        for line in found.get(label) or []:
            if len(lines) >= cap or line in lines:
                continue
            lines.append(line)
            took = True
        if took:
            sources.append(label)
    result = {"lines": lines, "sources": sources, "seconds": round(time.monotonic() - started, 1)}
    # Only a find is cached: an outage or a deadline must not hide the event for hours.
    if lines and not timed_out:
        set_cache(key, result, ttl_seconds=_CACHE_TTL)
    return result


def attach_event_research(
    signals: dict[str, Any] | None,
    *,
    topic: str,
    key_facts: list[str] | None,
    exclude_urls: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """(signals, report). The report is None when research did not run (off, or covered)."""
    base = dict(signals or {})
    try:
        if not research_enabled():
            return base, None
        before = precheck(topic, base, key_facts)
        if before is None or before.get("covered"):
            return base, None
        name = str(before["name"])
        found = research_event(name, exclude_urls=exclude_urls)
        lines = list(found.get("lines") or [])
        if lines:
            base[SIGNAL_NAME] = make_signal(
                connected=True,
                active=True,
                score=0,
                confidence=0.6,
                status=STATUS_OK,
                status_detail=f"Event research: {len(lines)} line(s) naming {name!r}",
                data={"name": name, "lines": lines, "sources": list(found.get("sources") or [])},
            )
        after = precheck(topic, base, key_facts)
        report = {
            "name": name,
            "before": False,
            "after": bool(after and after.get("covered")),
            "lines": len(lines),
            "sources": list(found.get("sources") or []),
            "seconds": found.get("seconds", 0),
        }
        return base, report
    except Exception as exc:  # research is a bonus; the guard still stands behind it
        logger.debug("event research skipped: %s", exc)
        return base, None


def report_line(report: dict[str, Any] | None) -> str:
    """One operator-facing line for the key-facts prompt and the run summary."""
    if not report:
        return ""
    name = report.get("name", "")
    if report.get("lines"):
        via = ", ".join(report.get("sources") or []) or "the web"
        return f"Found {report['lines']} line(s) naming '{name}' ({via}) - added to the facts."
    return (
        f"Nothing online names '{name}' yet - paste a link or facts now, "
        "or the run will stop before the voice."
    )
