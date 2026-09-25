"""#335: one outlet is a rumor, not a verified fact."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_URL = re.compile(r"https?://[^\s\]>)]+", re.I)
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


def urls_from_text(text: str) -> list[str]:
    return _URL.findall(text or "")


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
