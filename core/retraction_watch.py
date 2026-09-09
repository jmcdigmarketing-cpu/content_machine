"""#341: re-query stored source URLs for a retraction."""

from __future__ import annotations

import os
from collections.abc import Callable
from urllib.request import Request, urlopen

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.retraction_watch")


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


STAMP_PATH = os.path.join(DATA_DIR, "retraction_toast.json")


def toast_is_due(stamp_path: str | None = None, *, now=None) -> bool:
    """False when the last toast is under 24h old.

    Split out of `maybe_toast_retractions` so the caller can consult it *before*
    fetching: the watch pulls up to 12 URLs at an 8s timeout each, and `ops tray`
    calls it, so checking the stamp afterwards meant an interactive command could
    block for a minute and a half only to discover it had already toasted today.
    """
    from datetime import datetime, timedelta, timezone

    stamp = stamp_path or STAMP_PATH
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    try:
        import json
        import os as _os

        if not _os.path.isfile(stamp):
            return True
        with open(stamp, encoding="utf-8") as fh:
            raw = json.load(fh)
        last = datetime.fromisoformat(str(raw.get("last") or "").replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except Exception:
        return True
    return moment - last >= timedelta(hours=24)


def write_stamp(stamp_path: str, *, now=None) -> bool:
    """Persist the shared ``{"last": ISO}`` throttle shape."""
    from datetime import datetime, timezone

    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    try:
        import json
        import os as _os

        _os.makedirs(_os.path.dirname(stamp_path) or ".", exist_ok=True)
        with open(stamp_path, "w", encoding="utf-8") as fh:
            json.dump({"last": moment.isoformat()}, fh)
        return True
    except Exception as exc:
        logger.debug("retraction/correction stamp skipped: %s", exc)
        return False


def maybe_toast_retractions(
    hits: list[str],
    *,
    stamp_path: str | None = None,
    now=None,
    toaster=None,
) -> bool:
    """Toast the first hit at most once per 24h. CLI print path does not call this."""
    from datetime import datetime, timezone

    if not hits:
        return False
    stamp = stamp_path or STAMP_PATH
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    if not toast_is_due(stamp, now=moment):
        return False
    send = toaster
    if send is None:
        from core.win_notify import toast

        send = toast
    body = str(hits[0])[:180]
    send("Content OS retraction", body, key="retraction")
    write_stamp(stamp, now=moment)
    return True


def notify_retractions_if_due(channel_id: str | None = None, **kwargs) -> bool:
    """Overnight/tray caller. Skips the fetch when toasts are disabled (the suite)."""
    try:
        from core.win_notify import toast_enabled

        if kwargs.get("toaster") is None and not toast_enabled():
            return False
        # Before the fetch, not after it — see toast_is_due.
        if not toast_is_due(kwargs.get("stamp_path"), now=kwargs.get("now")):
            return False
        from core.review_booth import last_trace

        pairs = pairs_from_trace(last_trace(channel_id) or {})
        if not pairs:
            return False
        hits = watch_urls(pairs, fetch=kwargs.get("fetch"))
        return maybe_toast_retractions(
            hits,
            stamp_path=kwargs.get("stamp_path"),
            now=kwargs.get("now"),
            toaster=kwargs.get("toaster"),
        )
    except Exception:
        return False


def pairs_from_trace(trace: dict | None) -> list[tuple[str, str]]:
    """URLs from a run trace, claimed against the selected topic."""
    import json

    from core.source_diversity import urls_from_text

    payload = trace or {}
    topic = str(payload.get("selected_topic") or payload.get("input_topic") or "")
    structured = payload.get("source_urls")
    if isinstance(structured, list):
        urls = [str(url).strip() for url in structured if str(url).strip()]
        if urls:
            return [(url, topic) for url in urls[:12]]

    # Compatibility for legacy/synthetic traces. New production traces use the
    # structured field above; scraping the whole blob is no longer the contract.
    blob = json.dumps(payload, default=str)
    # The shared _URL pattern stops at whitespace / ] > ) — not at a quote or comma,
    # and this reads a JSON dump. Untrimmed, every URL arrives as `https://x/a",`
    # and every fetch 404s into the blanket handler, so the watch silently never
    # watched anything. Trim what JSON put there, keep the path intact.
    urls = [url.rstrip("\",'") for url in urls_from_text(blob)]
    return [(url, topic) for url in urls[:12] if url]
