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

import base64
import datetime as dt
import json
import os
import re
from typing import Any
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

from core.logging import get_logger
from core.operator_facts import (
    is_writing_tip,
    key_fact_split_width,
    parse_pasted_block,
    split_at_sentences,
)

logger = get_logger("core.link_facts")

_URL_RE = re.compile(r"^https?://\S+$", re.I)
# A bare User-Agent reads as a script to a surprising number of CDNs. Run 74 hit a
# 403 on Engadget; a browser-shaped header set clears the naive checks. It does not
# defeat a real WAF — the paste-recovery path in the fact prompt is that fix.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
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
    "college & high school",
    "free agency updates",
    "red-card timeline",
    "fights back tears",
    "dream ends in rout",
    "reportedly waive",
    "pens lakers goodbye",
    "staffer confesses",
    "kevin o'connor show",
    "intelligent search from bing",
    "makes it easier to quickly find",
)


_BLOCKED_URL_PARTS = (
    "bing.com/search",
    "well-known/sgcaptcha",
    "sgcaptcha",
)

_BLOCKED_TITLE_MARKERS = (
    "robot challenge",
    " - search",
    "captcha",
)


_ISO_DATE_PREFIX = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_META_DATE_KEYS: tuple[dict[str, Any], ...] = (
    {"property": "article:published_time"},
    {"property": "og:published_time"},
    {"name": "article:published_time"},
    {"itemprop": "datePublished"},
    {"name": "publish-date"},
    {"name": "pubdate"},
    {"name": "date"},
)


def _published_date(soup: BeautifulSoup) -> dt.date | None:
    """When the page says it was published, or None. Never raises.

    Run 74 stamped every scraped fact with no date at all, so ranking facts with a
    heavy recency bias had nothing to weigh. Fail-open by design: `None` means
    "unknown", which the selector treats as neutral rather than stale.
    """
    for attrs in _META_DATE_KEYS:
        tag = soup.find("meta", attrs=attrs)
        value = tag.get("content") if tag else None
        parsed = _parse_date(value)
        if parsed:
            return parsed

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or script.get_text() or "")
        except Exception as exc:
            logger.debug("ld+json date block unparseable for one script tag: %s", exc)
            continue
        for block in payload if isinstance(payload, list) else [payload]:
            if not isinstance(block, dict):
                continue
            parsed = _parse_date(block.get("datePublished") or block.get("dateCreated"))
            if parsed:
                return parsed

    for tag in soup.find_all("time"):
        parsed = _parse_date(tag.get("datetime"))
        if parsed:
            return parsed
    return None


def _parse_date(raw: object) -> dt.date | None:
    match = _ISO_DATE_PREFIX.match(str(raw or "").strip())
    if not match:
        return None
    try:
        return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _is_junk_line(text: str) -> bool:
    """True for promo/nav boilerplate or pure teaser questions — not a usable fact."""
    t = (text or "").strip()
    low = t.lower()
    if low.startswith("related:"):
        return True
    if any(m in low for m in _JUNK_MARKERS):
        return True
    # Teaser questions ("Will the Bucks move Giannis? Are X going anywhere?")
    return t.endswith("?") or t.count("?") >= 2


def _main_content_root(soup: BeautifulSoup):
    """Prefer article body over full-page scrape (sidebars, related links)."""
    for selector in (
        "article",
        "[role='main']",
        ".article-body",
        ".caas-body",
        "#article-body",
        "main",
    ):
        el = soup.select_one(selector)
        if el:
            return el
    return soup.body or soup


def _looks_like_trade_tracker(url: str, title: str) -> bool:
    u = (url or "").lower()
    t = (title or "").lower()
    return "trade" in u or "trade tracker" in t or "offseason trade" in t


def looks_like_url(text: str) -> bool:
    return bool(_URL_RE.match((text or "").strip()))


def _unwrap_redirect_url(url: str) -> str:
    """Follow Bing click-tracking wrappers to the destination URL when possible."""
    u = (url or "").strip()
    low = u.lower()
    if "bing.com/ck/" not in low:
        return u
    match = re.search(r"[?&]u=([^&]+)", u)
    if not match:
        return u
    raw = unquote(match.group(1))
    if raw.startswith("a1"):
        raw = raw[2:]
    try:
        pad = "=" * (-len(raw) % 4)
        decoded = base64.b64decode(raw + pad).decode("utf-8", errors="ignore")
    except Exception:
        return u
    return decoded if decoded.startswith("http") else u


def _is_blocked_url(url: str) -> bool:
    low = (url or "").lower()
    return any(part in low for part in _BLOCKED_URL_PARTS)


def _is_blocked_title(title: str) -> bool:
    low = (title or "").lower()
    return any(m in low for m in _BLOCKED_TITLE_MARKERS)


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


def _is_bot_blocked(resp: requests.Response) -> bool:
    """True when the host returned a WAF/challenge page instead of article HTML."""
    text = resp.text or ""
    if not text.strip():
        return True
    low = text.lower()
    if "awswaf" in low or ("window.aws" in low and "challenge" in low):
        return True
    # ESPN and similar sites often return 202 + empty title + a JS challenge shell.
    return resp.status_code == 202 and len(text) < 8000


def link_fetch_issue(url: str) -> str | None:
    """Human-readable reason a URL could not be scraped, or None if unknown/empty."""
    url = (url or "").strip()
    if not looks_like_url(url):
        return None
    if _is_blocked_url(url):
        if "bing.com/search" in url.lower():
            return (
                "Bing search pages cannot be scraped — paste the destination article URL instead."
            )
        return "That link is a bot-check or redirect page — paste the article URL or text manually."
    url = _unwrap_redirect_url(url)
    if _youtube_facts(url):
        return None
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12)
    except Exception as exc:
        logger.debug("link fetch failed for %s: %s", url, exc)
        return "Network error fetching that link — paste the text manually."
    if _is_bot_blocked(resp):
        host = url.split("/")[2] if "/" in url else "that site"
        return (
            f"{host} blocked automated fetch (bot protection) — "
            "copy/paste the article text as facts instead."
        )
    if resp.status_code != 200:
        logger.debug("link fetch %s returned %s", url, resp.status_code)
        return (
            f"Link returned HTTP {resp.status_code} — paste the article text, "
            "or set LINK_READER_PROXY=1 to try a proxy."
        )
    return None


def _extract_trade_lines(soup: BeautifulSoup) -> list[str]:
    """Pull list items and trade-shaped headings from sports tracker pages."""
    facts: list[str] = []
    for li in soup.find_all("li"):
        text = " ".join(li.get_text(" ", strip=True).split())
        if len(text) > 15 and not _is_junk_line(text):
            facts.extend(split_at_sentences(text, key_fact_split_width()))
    for tag in soup.find_all(["h2", "h3", "h4"]):
        text = " ".join(tag.get_text(" ", strip=True).split())
        if len(text) > 20 and re.search(r"\btrade", text, re.I) and not _is_junk_line(text):
            facts.extend(split_at_sentences(text, key_fact_split_width()))
    return facts


def _goose3_body_lines(url: str, html: str) -> list[str]:
    """Main-article paragraph lines via goose3 (raw_html — no extra fetch). [] on failure.

    goose3 is a maintained article-extraction library that isolates the primary article
    body and drops nav / sidebar / related-link chrome — cleaner than a blanket `<p>`
    scan. It parses the already-fetched HTML (`raw_html`), so there's no second network
    call and existing `requests.get` mocks stay authoritative. Returns raw lines; the
    caller applies the same junk / length / dedupe filters. Returns [] when goose3 is
    unavailable or yields nothing, so the caller falls back to its BeautifulSoup scan.
    """
    try:
        from goose3 import Goose
        from goose3.configuration import Configuration
    except Exception:
        return []  # goose3 not installed → BeautifulSoup fallback
    config = Configuration()
    config.strict = False
    config.browser_user_agent = _HEADERS["User-Agent"]
    config.http_timeout = 8.0
    try:
        with Goose(config) as g:
            article = g.extract(raw_html=html, url=url)
    except Exception as exc:
        logger.debug("goose3 extract failed for %s: %s", url, exc)
        return []
    text = (getattr(article, "cleaned_text", "") or "").strip()
    if not text:
        return []
    return [" ".join(line.split()) for line in text.split("\n") if line.strip()]


_last_extract_report: dict[str, Any] = {"kept": 0, "found": 0, "published": None}


def last_extract_report() -> dict[str, Any]:
    """What the most recent scrape found vs. returned, so the UI can say so.

    Run 74 scraped five articles at `max_lines=12` each and never mentioned the
    remainder - the Vice piece alone listed 150 details. A cap the operator cannot
    see is indistinguishable from a page that had nothing more to give.

    Also carries `published`, the page's own publication date, which is what lets
    the fact selector weight recency at all.
    """
    return dict(_last_extract_report)


def link_fact_max_lines() -> int:
    """Lines kept per scraped page (`LINK_FACT_MAX_LINES`, default 40, 5-200).

    The UI has told the operator to "raise the page cap" since run 74; until run 98
    there was nothing to raise - the cap was a literal.
    """
    try:
        value = int(os.getenv("LINK_FACT_MAX_LINES", "40") or 40)
    except ValueError:
        value = 40
    return max(5, min(200, value))


def _article_facts(url: str, *, max_lines: int | None = None) -> list[str]:
    """Fact lines from an article page: body paragraphs, plus its meta summary when
    the page HAS a body.

    The title is never a fact (run 98 sent six "Source: <title>" lines to the model
    and saved them to the vault as operator facts); it goes to `last_extract_report`
    for display and source capture. On a page with no body - a JS-rendered shell -
    the meta description is site boilerplate ("View Premier League club and player
    stats ... on the official website"), so the page returns no facts at all and
    `extract_facts_from_url` can try the reader proxy.
    """
    global _last_extract_report
    max_lines = max_lines if max_lines is not None else link_fact_max_lines()
    url = _unwrap_redirect_url(url)
    if _is_blocked_url(url):
        logger.debug("link fetch skipped blocked url %s", url)
        return []
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12)
        if resp.status_code != 200 or _is_bot_blocked(resp):
            blocked = _is_bot_blocked(resp)
            logger.debug("link fetch %s returned %s (blocked=%s)", url, resp.status_code, blocked)
            return []
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        logger.debug("link fetch failed for %s: %s", url, exc)
        return []

    root = _main_content_root(soup)
    published = _published_date(soup)
    facts: list[str] = []
    title = (soup.title.string if soup.title and soup.title.string else "").strip()
    if _is_blocked_title(title):
        logger.debug("link fetch rejected blocked title for %s: %s", url, title)
        return []

    # The meta summary leads the facts - but only if the page turns out to have a body.
    meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    summary: list[str] = []
    description = ""
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()
        if len(description) > 25 and not _is_junk_line(description):
            summary = split_at_sentences(description, key_fact_split_width())

    # Body paragraphs: goose3-first (cleaner main text, drops nav/sidebar chrome), with
    # the BeautifulSoup <p> scan as the fallback for JS-heavy / tiny pages. Trade-tracker
    # pages skip goose3 so the specialised <li>/heading extractor below still governs.
    body_lines: list[str] = []
    if not _looks_like_trade_tracker(url, title):
        body_lines = _goose3_body_lines(url, html)
    if not body_lines:
        body_lines = [" ".join(p.get_text(" ", strip=True).split()) for p in root.find_all("p")]
    for text in body_lines:
        if len(text) > 60 and not _is_junk_line(text):
            facts.extend(split_at_sentences(text, key_fact_split_width()))
    if facts:
        facts = summary + facts

    # List items only on trade-tracker pages — Yahoo/MSN sidebars are full of <li> noise.
    if _looks_like_trade_tracker(url, title):
        for trade_line in _extract_trade_lines(root):
            if trade_line.lower() not in {f.lower() for f in facts}:
                facts.append(trade_line)

    # De-duplicate, preserve order; drop writing tips.
    seen: set[str] = set()
    out: list[str] = []
    for f in facts:
        if is_writing_tip(f):
            continue
        key = f.lower()[:100]
        if key not in seen:
            seen.add(key)
            out.append(f)
    _last_extract_report = {
        "kept": min(len(out), max_lines),
        "found": len(out),
        "published": published,
        "title": title,
        "description": description,
    }
    return out[:max_lines]


def is_title_only(lines: list[str]) -> bool:
    """True when a scrape returned no real body — just a 'Source: <title>' line (or nothing).

    Lets the operator UI warn that a link (e.g. a JS-heavy MSN page) under-delivered so they
    paste the article text instead of shipping a script grounded only in a headline.
    """
    # "Source:" lines are no longer produced (run 98) but pre-existing callers and
    # vault text may still carry them.
    body = [ln for ln in (lines or []) if not ln.lower().startswith("source:")]
    return not body


def _reader_proxy_enabled() -> bool:
    return os.getenv("LINK_READER_PROXY", "").lower() in ("1", "true", "yes")


def _reader_proxy_facts(url: str, *, max_lines: int = 12) -> list[str]:
    """Rendered page text via the r.jina.ai reader proxy — handles JS-heavy pages (MSN).

    OPT-IN (`LINK_READER_PROXY`) and off by default: this sends the target URL to a
    third-party service (r.jina.ai), which is why it isn't on in the self-hosted-first
    default. Fail-open → [] on any error; applies the same junk/tip filters as the scraper.
    """
    try:
        resp = requests.get(f"https://r.jina.ai/{url}", headers=_HEADERS, timeout=15)
        if resp.status_code != 200 or not (resp.text or "").strip():
            return []
        text = resp.text
    except Exception as exc:
        logger.debug("reader proxy failed for %s: %s", url, exc)
        return []
    facts: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        ln = " ".join(line.lstrip("#>*-• ").split())  # strip markdown chrome
        if len(ln) <= 60 or _is_junk_line(ln) or is_writing_tip(ln):
            continue
        key = ln.lower()[:100]
        if key not in seen:
            seen.add(key)
            facts.extend(split_at_sentences(ln, key_fact_split_width()))
        if len(facts) >= max_lines:
            break
    return facts


def extract_facts_from_url(url: str) -> list[str]:
    """Best-effort fact extraction from a URL. Returns [] on any failure."""
    global _last_extract_report
    _last_extract_report = {
        "kept": 0,
        "found": 0,
        "published": None,
        "title": "",
        "description": "",
    }
    url = (url or "").strip()
    if not looks_like_url(url):
        return []
    if _is_blocked_url(url):
        return []
    url = _unwrap_redirect_url(url)
    yt = _youtube_facts(url)
    if yt:
        return yt
    raw = _article_facts(url)
    # JS-heavy pages (e.g. MSN) scrape to only a title — retry via the opt-in reader proxy.
    if is_title_only(raw) and _reader_proxy_enabled():
        proxied = _reader_proxy_facts(url)
        if proxied:
            raw = proxied
            _last_extract_report["kept"] = _last_extract_report["found"] = len(proxied)
    # Compact duplicate intros from meta + first paragraph.
    return parse_pasted_block("\n".join(raw)) or raw
