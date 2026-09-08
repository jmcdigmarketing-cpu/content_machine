"""#341: re-query stored source URLs for a retraction."""

from __future__ import annotations

from collections.abc import Callable
from urllib.request import Request, urlopen


def _default_fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "content-os-retraction-watch/1"})
    with urlopen(req, timeout=8) as resp:
        return resp.read(8000).decode("utf-8", errors="replace")


def watch_urls(
    pairs: list[tuple[str, str]],
    *,
    fetch: Callable[[str], str] | None = None,
) -> list[str]:
    """Return hit lines when the live body no longer contains the stored claim."""
    getter = fetch or _default_fetch
    hits: list[str] = []
    for url, claim in pairs:
        body = getter(url)
        blob = body.lower()
        needle = (claim or "").strip()
        if "retraction" in blob or "retracted" in blob:
            hits.append(f"{url}: RETRACTION in live body")
            continue
        if needle and needle.lower() not in blob:
            hits.append(f"{url}: stored claim missing from live body")
    return hits


def pairs_from_trace(trace: dict | None) -> list[tuple[str, str]]:
    """URLs from a run trace, claimed against the selected topic."""
    import json

    from core.source_diversity import urls_from_text

    payload = trace or {}
    topic = str(payload.get("selected_topic") or payload.get("input_topic") or "")
    blob = json.dumps(payload, default=str)
    urls = urls_from_text(blob)
    return [(url, topic) for url in urls[:12]]
