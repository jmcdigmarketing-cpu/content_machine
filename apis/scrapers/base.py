"""Shared helpers for reference-site scrapers (Basketball Reference, PFR, etc.)."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CACHE_DIR = os.path.join("data", "scraper_cache")


def scrape_enabled() -> bool:
    return os.getenv("STATS_SCRAPE_ENABLED", "true").lower() not in (
        "0",
        "false",
        "no",
    )


def cache_path(source: str) -> str:
    return os.path.join(CACHE_DIR, f"{source}.json")


def load_cache(source: str) -> dict:
    path = cache_path(source)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def get_cached(source: str, key: str, *, ttl_seconds: int) -> Any | None:
    entry = load_cache(source).get(key.strip().lower()[:120])
    if not entry:
        return None
    if time.time() - float(entry.get("ts", 0)) > ttl_seconds:
        return None
    return entry.get("data")


def set_cached(source: str, key: str, data: Any) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = load_cache(source)
    cache[key.strip().lower()[:120]] = {"ts": time.time(), "data": data}
    with open(cache_path(source), "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def search_query_from_topic(topic: str, *, max_len: int = 48) -> str:
    """Short query for site search boxes."""
    text = re.sub(r"\b(20\d{2}|vs\.?|versus|preview|analysis|why|how)\b", "", topic, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" .,-")
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0]
    return text or topic.strip()[:max_len]


def detect_stat_domains(topic: str) -> list[str]:
    t = (topic or "").lower()
    domains: list[str] = []
    if any(
        k in t
        for k in (
            "nba",
            "basketball",
            "finals",
            "playoffs",
            "wembanyama",
            "knicks",
            "lakers",
            "celtics",
            "draft",
        )
    ):
        domains.append("nba")
    if any(
        k in t
        for k in (
            "nfl",
            "football",
            "super bowl",
            "quarterback",
            "touchdown",
            "mahomes",
            "chiefs",
            "garrett",
            "rams",
            "chargers",
        )
    ):
        domains.append("nfl")
    if any(k in t for k in ("ufc", "mma", "fight card", "tapology", "bout", "ppv")):
        domains.append("mma")
    return domains


def fetch_html(session: requests.Session, url: str, *, timeout: int = 12) -> str | None:
    try:
        resp = session.get(url, headers=HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return None
        return resp.text
    except requests.RequestException:
        return None


def lines_from_table(soup: BeautifulSoup, table_id: str, *, max_rows: int = 2) -> list[str]:
    table = soup.find("table", id=table_id)
    if not table:
        return []
    rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")
    lines: list[str] = []
    for row in rows[:max_rows]:
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
        cells = [c for c in cells if c]
        if cells:
            lines.append(" | ".join(cells[:12]))
    return lines
