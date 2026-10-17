"""#335: one outlet is a rumor, not a verified fact."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_URL = re.compile(r"https?://[^\s\]>)]+", re.I)
_URL_TAIL = "\"'}),.;"
_NOT_A_PAGE_RE = re.compile(
    r"\.(?:jpe?g|png|gif|webp|svg|ico|mp4|webm|m3u8|css|js)(?:$|[?#])", re.I
)
_MEDIA_HOST_RE = re.compile(r"(?:^|[.-])(?:cdn|static|img|images?|media)(?:[.-]|\d)", re.I)
_NEWS_CUES = re.compile(
    r"\b("
    r"20\d{2}|january|february|march|april|june|july|august|september|"
    r"october|november|december|saturday|sunday|monday|tuesday|wednesday|"
    r"thursday|friday|ufc\s+\d+|results|leaked|announced|broke|reports?\b"
    r")",
    re.I,
)
_EVERGREEN = re.compile(r"\bhow does\b|\bwhat is\b|\bwhy do\b|\bexplained\b", re.I)


def registrable_domain(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def unique_domains(urls: list[str]) -> frozenset[str]:
    return frozenset(d for d in (registrable_domain(u) for u in urls if u) if d)


def is_page_url(url: str) -> bool:
    """False for a picture, a media file, a CDN host or a template with braces (#1157).

    50 of 71 stored source links were of this kind - coin images, Twitch box art, last.fm
    thumbnails read out of a signal's raw data. Each counted as an outlet, and the nightly
    correction scan tried to read each one as an article.
    """
    text = str(url or "")
    if not text.lower().startswith(("http://", "https://")) or "{" in text or "%7b" in text.lower():
        return False
    parsed = urlparse(text)
    if _NOT_A_PAGE_RE.search(parsed.path or ""):
        return False
    return not _MEDIA_HOST_RE.search(parsed.netloc or "")


_REFUSE_IN_URL = ('"', "'", "{", "}")


def clean_urls(urls: list[str]) -> list[str]:
    """Pages only. A URL that still contains a quote or a brace is not fetched (#1227).

    Stripping the quote and fetching the page left Last.fm and Twitch box-art
    templates in the correction scan, which retried them every run.
    """
    out: list[str] = []
    for raw in urls or []:
        text = str(raw or "").strip()
        if any(mark in text for mark in _REFUSE_IN_URL):
            continue
        url = text.rstrip(_URL_TAIL)
        if url and is_page_url(url) and url not in out:
            out.append(url)
    return out


def urls_from_text(text: str) -> list[str]:
    """URLs in prose. A quote or brace that closed the surrounding text is not part of the URL."""
    stripped = [match.strip().rstrip(_URL_TAIL) for match in _URL.findall(text or "")]
    return clean_urls(stripped)


def is_news_shaped(topic: str) -> bool:
    text = topic or ""
    if _EVERGREEN.search(text):
        return False
    return bool(_NEWS_CUES.search(text))


def source_diversity_ok(urls: list[str], *, topic: str) -> bool:
    """False when a news-shaped topic is backed by a single registrable domain."""
    if not is_news_shaped(topic):
        return True
    domains = unique_domains(urls)
    if not domains:
        return True
    return len(domains) >= 2


def demote_single_outlet_news(
    verified: str,
    *,
    urls: list[str],
    topic: str,
) -> tuple[str, str, dict[str, str]]:
    """Move single-outlet news out of verified. Evergreen topics are untouched."""
    combined = list(urls) + urls_from_text(verified)
    if source_diversity_ok(combined, topic=topic):
        return verified or "", "", {"status": "ok", "domain": ""}
    domains = unique_domains(combined)
    domain = next(iter(sorted(domains))) if domains else ""
    return "", verified or "", {"status": "single_outlet", "domain": domain}


def singleton_source_claims(rows: list[tuple[str, list[str]]]) -> list[str]:
    """Flag claims that rest on one host when the batch has two or more hosts."""
    all_urls = [u for _claim, urls in rows for u in urls]
    if len(unique_domains(all_urls)) < 2:
        return []
    flags: list[str] = []
    for claim, urls in rows:
        domains = unique_domains(urls)
        if len(domains) == 1:
            flags.append(f"{claim.strip()} (only {next(iter(sorted(domains)))})")
    return flags
