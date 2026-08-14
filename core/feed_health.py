"""RSS feed health — catch dead sources before they starve a script.

Why this exists: on 2026-08-14 an audit found **11 of ~37 configured feeds dead**
(404s, a 403, ESPN's `202`-with-empty-body, a dead host) and one *live* feed silently
dropped by a BOM parse error — and the pipeline had reported none of it for over a
month. `fetch_rss_context` buries per-feed failures in an `errors[:3]` field nobody
reads and still returns `connected: True`, so a starved research brief is
indistinguishable from a quiet news day.

Three outcomes, because "alive" is not the same as "useful":

- `ok`    — fetched, parsed, and has a recent item
- `stale` — fetched and parsed, but the newest item is older than the staleness window
            (a feed that quietly stopped updating; previously invisible)
- `dead`  — unreachable, non-200, or parsed to zero items

Read-only and fail-open: a checker error is reported as a `dead` row, never raised.
Network access is deliberate here, so the test suite mocks HTTP rather than hitting
the live web (`tests/CLAUDE.md`).
"""

from __future__ import annotations

import glob
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import requests

from apis.rss_feeds import _parse_feed_xml, decode_feed_bytes
from core.logging import get_logger

logger = get_logger("core.feed_health")

_TIMEOUT = 12
_MAX_WORKERS = 8

STATUS_OK = "ok"
STATUS_STALE = "stale"
STATUS_DEAD = "dead"

_HEADERS = {
    "User-Agent": "ContentMachine/1.0 (+https://localhost; research/rss)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def stale_after_days() -> int:
    try:
        return max(1, int(os.getenv("FEED_STALE_DAYS", "14")))
    except ValueError:
        return 14


def iter_configured_feeds() -> list[dict[str, str]]:
    """Every feed the pipeline can read: config/data_sources.json + config/seo/*.json.

    De-duplicated by URL — the same feed is often both a channel feed and a domain
    feed, and it only needs checking once.
    """
    feeds: list[dict[str, str]] = []

    def _add(scope: str, entry: Any) -> None:
        if not isinstance(entry, dict):
            return
        url = str(entry.get("url") or "").strip()
        if url:
            feeds.append({"scope": scope, "name": str(entry.get("name") or url), "url": url})

    try:
        with open(os.path.join("config", "data_sources.json"), encoding="utf-8") as fh:
            sources = json.load(fh)
        for entry in sources.get("global_rss") or []:
            _add("global", entry)
        for domain, entries in (sources.get("domain_rss") or {}).items():
            for entry in entries or []:
                _add(f"domain:{domain}", entry)
    except Exception as exc:
        logger.debug("data_sources.json unreadable: %s", exc)

    for path in sorted(glob.glob(os.path.join("config", "seo", "*.json"))):
        channel = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path, encoding="utf-8") as fh:
                config = json.load(fh)
            for entry in config.get("rss_feeds") or []:
                _add(f"seo:{channel}", entry)
        except Exception as exc:
            logger.debug("%s unreadable: %s", path, exc)

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for feed in feeds:
        if feed["url"] in seen:
            continue
        seen.add(feed["url"])
        unique.append(feed)
    return unique


def _newest_age_days(items: list[dict[str, str]]) -> float | None:
    """Age in days of the most recent item, or None when no item carries a date."""
    from core.best_bet import _parse_pubdate

    newest: datetime | None = None
    for item in items:
        parsed = _parse_pubdate(item.get("published"))
        if parsed is None:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if newest is None or parsed > newest:
            newest = parsed
    if newest is None:
        return None
    # Clamp: some feeds carry future-dated items, and a negative age reads as a bug.
    return max(0.0, (datetime.now(timezone.utc) - newest).total_seconds() / 86400.0)


def check_feed(feed: dict[str, str], *, timeout: int = _TIMEOUT) -> dict[str, Any]:
    """Fetch and classify one feed. Never raises."""
    result: dict[str, Any] = {
        "scope": feed.get("scope", ""),
        "name": feed.get("name", ""),
        "url": feed.get("url", ""),
        "status": STATUS_DEAD,
        "http": 0,
        "items": 0,
        "age_days": None,
        "detail": "",
    }
    try:
        resp = requests.get(result["url"], headers=_HEADERS, timeout=timeout, allow_redirects=True)
        result["http"] = resp.status_code
        if resp.status_code != 200:
            result["detail"] = f"HTTP {resp.status_code}"
            return result
        items = _parse_feed_xml(decode_feed_bytes(resp.content), url=result["url"])
        result["items"] = len(items)
        if not items:
            # ESPN's retired feeds answer 202 with an empty body; a malformed feed
            # parses to zero. Either way there is nothing to ground a script in.
            result["detail"] = "no items parsed"
            return result

        age = _newest_age_days(items)
        result["age_days"] = age
        if age is not None and age > stale_after_days():
            result["status"] = STATUS_STALE
            result["detail"] = f"newest item {age:.0f}d old"
            return result
        result["status"] = STATUS_OK
        return result
    except Exception as exc:
        result["detail"] = f"{type(exc).__name__}: {exc}"
        return result


def check_feeds(
    feeds: list[dict[str, str]] | None = None, *, timeout: int = _TIMEOUT
) -> list[dict[str, Any]]:
    """Check every configured feed concurrently. Fail-open: returns [] on any error."""
    try:
        targets = feeds if feeds is not None else iter_configured_feeds()
        if not targets:
            return []
        with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(targets))) as pool:
            return list(pool.map(lambda f: check_feed(f, timeout=timeout), targets))
    except Exception as exc:
        logger.debug("feed health check failed: %s", exc)
        return []


def save_results(results: list[dict[str, Any]]) -> None:
    """Persist the last check so `ops reliability` can report rot without re-fetching.

    The dashboard must stay fast and read-only; re-running 37 HTTP requests every time
    the operator glances at it is not acceptable, so `ops feeds` writes and the
    dashboard reads.
    """
    try:
        from config.paths import FEED_HEALTH_FILE, ensure_data_dir

        ensure_data_dir()
        payload = {"checked_at": datetime.now(timezone.utc).isoformat(), "results": results}
        with open(FEED_HEALTH_FILE, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    except Exception as exc:
        logger.debug("could not save feed health: %s", exc)


def load_results() -> dict[str, Any]:
    """Last persisted check, or {} when never run. Never raises."""
    try:
        from config.paths import FEED_HEALTH_FILE

        if not os.path.exists(FEED_HEALTH_FILE):
            return {}
        with open(FEED_HEALTH_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.debug("could not load feed health: %s", exc)
        return {}


def cached_warnings() -> list[str]:
    """Warnings from the last persisted check — no network. [] when never run."""
    data = load_results()
    results = data.get("results") or []
    if not results:
        return []
    out = warnings(results)
    if not out:
        return []
    checked = str(data.get("checked_at") or "")
    age_note = ""
    try:
        when = datetime.fromisoformat(checked)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - when).days
        if days >= 7:
            age_note = f" (feed check is {days}d old — run 'ops feeds')"
    except Exception:
        pass
    if age_note:
        out = [line + age_note if i == 0 else line for i, line in enumerate(out)]
    return out


def summarize(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {STATUS_OK: 0, STATUS_STALE: 0, STATUS_DEAD: 0}
    for row in results or []:
        status = str(row.get("status") or STATUS_DEAD)
        counts[status] = counts.get(status, 0) + 1
    return counts


def warnings(results: list[dict[str, Any]]) -> list[str]:
    """Operator-facing lines for dead/stale feeds — consumed by core.data_quality."""
    out: list[str] = []
    for row in results or []:
        status = row.get("status")
        if status == STATUS_DEAD:
            out.append(
                f"RSS feed dead: {row.get('name')} ({row.get('scope')}) — {row.get('detail')}"
            )
        elif status == STATUS_STALE:
            out.append(
                f"RSS feed stale: {row.get('name')} ({row.get('scope')}) — {row.get('detail')}"
            )
    return out


def render(results: list[dict[str, Any]] | None = None) -> str:
    if results is None:
        results = check_feeds()
    if not results:
        return "No RSS feeds configured (or the check could not run)."

    counts = summarize(results)
    lines = [
        "",
        "RSS feed health",
        "=" * 72,
        # Plain ASCII: the Windows console is cp1252 and mangles decorative separators.
        f"  {counts[STATUS_OK]} ok / {counts[STATUS_STALE]} stale / {counts[STATUS_DEAD]} dead"
        f"   (stale = no item in {stale_after_days()}d)",
        "",
    ]
    rank = {STATUS_DEAD: 0, STATUS_STALE: 1, STATUS_OK: 2}
    for row in sorted(
        results, key=lambda r: (rank.get(str(r.get("status")), 3), str(r.get("scope")))
    ):
        status = str(row.get("status"))
        mark = {STATUS_OK: "ok  ", STATUS_STALE: "STALE", STATUS_DEAD: "DEAD"}.get(status, "?")
        age = row.get("age_days")
        age_text = f"{age:.0f}d" if isinstance(age, int | float) else "-"
        lines.append(
            f"  {mark:5} {str(row.get('scope'))[:14]:14} {str(row.get('name'))[:24]:24} "
            f"items={row.get('items'):>3}  newest={age_text:>5}  {str(row.get('detail'))[:34]}"
        )
    if counts[STATUS_DEAD] or counts[STATUS_STALE]:
        lines += ["", "  Fix dead feeds in config/data_sources.json or config/seo/<channel>.json."]
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    results = check_feeds()
    save_results(results)
    print(render(results))
    # Non-zero exit when a feed is dead so `ops all-checks` surfaces it.
    return 1 if summarize(results).get(STATUS_DEAD) else 0


if __name__ == "__main__":
    raise SystemExit(main())
