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


def maybe_toast_retractions(
    hits: list[str],
    *,
    stamp_path: str | None = None,
    now=None,
    toaster=None,
) -> bool:
    """Toast the first hit at most once per 24h. CLI print path does not call this."""
    from datetime import datetime, timedelta, timezone

    if not hits:
        return False
    stamp = stamp_path or STAMP_PATH
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    last = None
    try:
        import json
        import os as _os

        if _os.path.isfile(stamp):
            with open(stamp, encoding="utf-8") as fh:
                raw = json.load(fh)
            last = datetime.fromisoformat(str(raw.get("last") or "").replace("Z", "+00:00"))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
    except Exception:
        last = None
    if last is not None and moment - last < timedelta(hours=24):
        return False
    send = toaster
    if send is None:
        from core.win_notify import toast

        send = toast
    body = str(hits[0])[:180]
    send("Content OS retraction", body, key="retraction")
    try:
        import json
        import os as _os

        _os.makedirs(_os.path.dirname(stamp) or ".", exist_ok=True)
        with open(stamp, "w", encoding="utf-8") as fh:
            json.dump({"last": moment.isoformat()}, fh)
    except Exception as exc:
        logger.debug("retraction toast stamp skipped: %s", exc)
    return True


def notify_retractions_if_due(channel_id: str | None = None, **kwargs) -> bool:
    """Overnight/tray caller. Skips the fetch when toasts are disabled (the suite)."""
    try:
        from core.win_notify import toast_enabled

        if kwargs.get("toaster") is None and not toast_enabled():
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
    blob = json.dumps(payload, default=str)
    urls = urls_from_text(blob)
    return [(url, topic) for url in urls[:12]]
