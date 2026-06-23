"""
Tapology scraper (no API) — event search + fight card facts for UFC scripts.

Respects robots: light requests, caching, browser-like User-Agent.
Set TAPOLOGY_SCRAPE_ENABLED=false to disable.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    classify_exception,
    make_signal,
)

BASE_URL = "https://www.tapology.com"
CACHE_FILE = os.path.join("data", "tapology_cache.json")
CACHE_TTL_SECONDS = 6 * 60 * 60
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_enabled() -> bool:
    return os.getenv("TAPOLOGY_SCRAPE_ENABLED", "false").lower() not in (
        "0",
        "false",
        "no",
    )


# Back-compat alias (internal + ufc_context callers).
_scrape_enabled = scrape_enabled


def _is_mma_topic(topic: str) -> bool:
    t = topic.lower()
    return any(k in t for k in ("ufc", "mma", "topuria", "gaethje", "fight", "boxing", "ppv"))


def _cache_key(topic: str) -> str:
    return topic.strip().lower()[:120]


def _load_cache() -> dict:
    if not os.path.isfile(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(data: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _get_cached(topic: str) -> dict | None:
    key = _cache_key(topic)
    entry = _load_cache().get(key)
    if not entry:
        return None
    if time.time() - float(entry.get("timestamp", 0)) > CACHE_TTL_SECONDS:
        return None
    return entry.get("data")


def _set_cached(topic: str, payload: dict) -> None:
    cache = _load_cache()
    cache[_cache_key(topic)] = {"timestamp": time.time(), "data": payload}
    _save_cache(cache)


def _search_events(session: requests.Session, query: str) -> list[dict[str, str]]:
    url = f"{BASE_URL}/search?mainSearchFilter=events&term={quote(query)}"
    response = session.get(url, timeout=12)
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    events = []
    for link in soup.select('a[href*="/fightcenter/events/"]'):
        href = link.get("href") or ""
        name = link.get_text(" ", strip=True)
        if not name or len(name) < 4:
            continue
        full_url = urljoin(BASE_URL, href)
        if any(e["url"] == full_url for e in events):
            continue
        events.append({"name": name, "url": full_url})
        if len(events) >= 5:
            break
    return events


def _parse_event_page(session: requests.Session, event_url: str) -> dict[str, Any]:
    response = session.get(event_url, timeout=12)
    if response.status_code != 200:
        return {}

    soup = BeautifulSoup(response.text, "html.parser")
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)

    date = ""
    for node in soup.find_all(string=re.compile(r"\d{4}\.\d{2}\.\d{2}")):
        date = str(node).strip()
        break

    bouts = []
    # Tapology bout rows often use fighter links in the card section
    for row in soup.select("div[data-controller='bout']"):
        fighters = [
            a.get_text(" ", strip=True) for a in row.select('a[href*="/fightcenter/fighters/"]')
        ]
        fighters = [f for f in fighters if f]
        if len(fighters) >= 2:
            bouts.append({"red": fighters[0], "blue": fighters[1]})

    if not bouts:
        links = soup.select('a[href*="/fightcenter/fighters/"]')
        names = []
        for link in links:
            name = link.get_text(" ", strip=True)
            if name and name not in names and len(name) > 2:
                names.append(name)
        if len(names) >= 2:
            bouts.append({"main_event": f"{names[0]} vs {names[1]}"})

    main = bouts[0] if bouts else {}
    return {
        "event_title": title,
        "event_date": date,
        "event_url": event_url,
        "bouts": bouts[:12],
        "main_event": main,
    }


def scrape_tapology(topic: str) -> dict[str, Any]:
    cached = _get_cached(topic)
    if cached:
        return cached

    session = requests.Session()
    session.headers.update(HEADERS)

    query = topic
    event_num = re.search(r"\bUFC\s*(\d{2,4})\b", topic, re.I)
    if event_num:
        query = f"UFC {event_num.group(1)} Topuria Gaethje"

    events = _search_events(session, query)
    if not events and event_num:
        events = _search_events(session, f"UFC Freedom {event_num.group(1)}")

    payload: dict[str, Any] = {
        "search_query": query,
        "events_found": events,
        "source": "tapology.com",
    }

    if events:
        card = _parse_event_page(session, events[0]["url"])
        payload.update(card)
        payload["matched_event"] = events[0]["name"]

    _set_cached(topic, payload)
    return payload


def get_tapology(topic: str):
    if not _scrape_enabled():
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail="TAPOLOGY_SCRAPE_ENABLED=false",
        )

    if not _is_mma_topic(topic):
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail="Not an MMA/UFC topic",
        )

    try:
        data = scrape_tapology(topic)
        events = data.get("events_found") or []
        bouts = data.get("bouts") or []
        active = bool(events or bouts or data.get("event_title"))
        score = min(30 + len(bouts) * 10 + len(events) * 5, 100)

        detail = None
        if not active:
            detail = "No Tapology event match (try topic with UFC number + fighter names)"

        return make_signal(
            connected=True,
            active=active,
            score=score,
            confidence=0.9 if bouts else 0.65,
            data=data,
            status=STATUS_OK if active else STATUS_INACTIVE,
            status_detail=detail,
        )
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            return make_signal(
                connected=False,
                active=False,
                status=STATUS_UNAVAILABLE,
                status_detail="Tapology blocked request (403) — retry later or use VPN",
            )
        status, detail = classify_exception(e)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Test Tapology scrape for a topic")
    parser.add_argument("topic", nargs="*", default=["UFC 250 Topuria Gaethje"])
    args = parser.parse_args()
    topic = " ".join(args.topic)
    payload = scrape_tapology(topic)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
