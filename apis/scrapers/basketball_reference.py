"""Basketball Reference search + per-game stat snippets (no API key)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from apis.scrapers.base import (
    fetch_html,
    get_cached,
    search_query_from_topic,
    set_cached,
)

BASE = "https://www.basketball-reference.com"
TTL = 6 * 60 * 60


def fetch_bref_stats(topic: str) -> dict[str, Any]:
    query = search_query_from_topic(topic)
    cached = get_cached("bref", query, ttl_seconds=TTL)
    if cached is not None:
        return cached

    result: dict[str, Any] = {"query": query, "lines": [], "entity": "", "url": ""}
    session = requests.Session()

    search_url = f"{BASE}/search/search.fcgi?search={quote(query)}"
    html = fetch_html(session, search_url)
    if not html:
        set_cached("bref", query, result)
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
        set_cached("bref", query, result)
        return result

    page = fetch_html(session, link)
    if not page:
        set_cached("bref", query, result)
        return result

    psoup = BeautifulSoup(page, "html.parser")
    lines: list[str] = []
    title = psoup.find("h1")
    if title:
        lines.append(title.get_text(" ", strip=True))

    for table_id in ("per_game", "totals", "games"):
        tbody = psoup.find("table", id=table_id)
        if not tbody:
            continue
        row = tbody.find("tbody")
        tr = row.find("tr") if row else tbody.find("tr")
        if tr:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            cells = [c for c in cells if c and not re.match(r"^\d{4}-\d{2}$", c)]
            if len(cells) >= 4:
                lines.append(f"{table_id}: " + " | ".join(cells[:10]))
                break

    result = {
        "query": query,
        "entity": entity,
        "url": link,
        "lines": lines[:4],
        "source": "Basketball Reference",
    }
    set_cached("bref", query, result)
    return result
