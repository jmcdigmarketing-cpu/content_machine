"""Turn a pasted link into verified fact lines for the key-facts prompt.

When an operator pastes a URL where facts are expected, the raw URL is useless to
the LLM (it can't open it). This module fetches the link and extracts a few
fact-shaped lines instead:

  - YouTube links -> the video's title + key description lines (via the YouTube API).
  - Article/other links -> the page title + first meaningful paragraphs (BeautifulSoup).

Always returns a list (possibly empty) and never raises, so callers can treat any
input line uniformly.
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from core.logging import get_logger

logger = get_logger("core.link_facts")

_URL_RE = re.compile(r"^https?://\S+$", re.I)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


# Promo / nav / boilerplate substrings that mark a line as non-factual. Index
# pages (e.g. cbssports.com/nba/) are full of these; they poison the fact corpus
# and, worse, give the model nothing solid so it fills gaps by inventing.
_JUNK_MARKERS = (
    "has the latest",
    "sign up",
    "subscribe",
    "newsletter",
    "cookie",
    "all rights reserved",
    "click here",
    "terms of",
    "privacy policy",
    "advertisement",
    "log in",
    "logged in",
    "create an account",
    "fantasy games",
    "©",
)


def _is_junk_line(text: str) -> bool:
    """True for promo/nav boilerplate or pure teaser questions — not a usable fact."""
    t = (text or "").strip()
    low = t.lower()
    if any(m in low for m in _JUNK_MARKERS):
        return True
    # Teaser questions ("Will the Bucks move Giannis? Are X going anywhere?")
    return t.endswith("?") or t.count("?") >= 2


def looks_like_url(text: str) -> bool:
    return bool(_URL_RE.match((text or "").strip()))


def _youtube_facts(url: str) -> list[str]:
    from apis.youtube_api import extract_youtube_video_id, fetch_video_metadata

    if not extract_youtube_video_id(url):
        return []
    meta = fetch_video_metadata(url)
    if not meta:
        return []
    facts: list[str] = []
    title = (meta.get("title") or "").strip()
    channel = (meta.get("channel") or "").strip()
    if title:
        facts.append(f'Source video: "{title}"' + (f" by {channel}" if channel else ""))
    # Pull a few meaningful description lines (skip links/boilerplate).
    for line in (meta.get("description") or "").splitlines():
        line = line.strip()
        if len(line) > 25 and "http" not in line.lower():
            facts.append(line)
        if len(facts) >= 5:
            break
    return facts


def _article_facts(url: str, *, max_lines: int = 5) -> list[str]:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12)
        if resp.status_code != 200:
            logger.debug("link fetch %s returned %s", url, resp.status_code)
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.debug("link fetch failed for %s: %s", url, exc)
        return []

    facts: list[str] = []
    title = (soup.title.string if soup.title and soup.title.string else "").strip()
    if title:
        facts.append(f"Source: {title}")

    # Prefer the meta description, then the first substantial paragraphs.
    meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    if meta_desc and meta_desc.get("content"):
        content = meta_desc["content"].strip()
        if len(content) > 25 and not _is_junk_line(content):
            facts.append(content[:300])

    for p in soup.find_all("p"):
        text = " ".join(p.get_text(" ", strip=True).split())
        if len(text) > 60 and not _is_junk_line(text):
            facts.append(text[:300])
        if len(facts) >= max_lines:
            break

    # De-duplicate, preserve order.
    seen: set[str] = set()
    out: list[str] = []
    for f in facts:
        if f.lower() not in seen:
            seen.add(f.lower())
            out.append(f)
    return out[:max_lines]


def extract_facts_from_url(url: str) -> list[str]:
    """Best-effort fact extraction from a URL. Returns [] on any failure."""
    url = (url or "").strip()
    if not looks_like_url(url):
        return []
    yt = _youtube_facts(url)
    if yt:
        return yt
    return _article_facts(url)
