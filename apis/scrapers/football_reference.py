"""Pro-Football-Reference search + recent season stat line (no API key)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from apis.scrapers.base import fetch_html, get_cached, search_query_from_topic, set_cached

BASE = "https://www.pro-football-reference.com"
TTL = 6 * 60 * 60


def fetch_pfr_stats(topic: str) -> dict[str, Any]:
    query = search_query_from_topic(topic)
    cached = get_cached("pfr", query, ttl_seconds=TTL)
    if cached is not None:
        return cached

    result: dict[str, Any] = {"query": query, "lines": [], "entity": "", "url": ""}
    session = requests.Session()

    search_url = f"{BASE}/search/search.fcgi?search={quote(query)}"
    html = fetch_html(session, search_url)
    if not html:
        set_cached("pfr", query, result)
        return result

    soup = BeautifulSoup(html, "html.parser")
    link = None
    entity = ""
    for item in soup.select("div.search-item"):
        a = item.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        if "/players/" in href or "/teams/" in href:
            link = urljoin(BASE, href)
            entity = a.get_text(" ", strip=True)
            break

    if not link:
        set_cached("pfr", query, result)
        return result

    page = fetch_html(session, link)
    if not page:
        set_cached("pfr", query, result)
        return result

    psoup = BeautifulSoup(page, "html.parser")
    lines: list[str] = []
    title = psoup.find("h1")
    if title:
        lines.append(title.get_text(" ", strip=True))

    for table_id in ("stats", "receiving_and_rushing", "passing"):
        table = psoup.find("table", id=table_id)
        if not table:
            continue
        tbody = table.find("tbody")
        tr = tbody.find("tr") if tbody else table.find("tr")
        if tr:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if len(cells) >= 4:
                lines.append(f"{table_id}: " + " | ".join(cells[:10]))
                break

    result = {
        "query": query,
        "entity": entity,
        "url": link,
        "lines": lines[:4],
        "source": "Pro-Football-Reference",
    }
    set_cached("pfr", query, result)
    return result
