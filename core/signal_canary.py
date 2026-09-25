"""Signal liveness canary (#383) — exercise every signal at zero spend.

`tapology` answered "no event match" for **33 days** while actually taking a
Cloudflare 403, and `twitter` went 19/19 runs returning zero facts. Neither
crashed, so every run looked fine. Decision §18 settled the principle — a source
that cannot answer must report *failure*, not "no match" — but nothing exercises
the sources between real runs, so a dead one is still discovered by a run that
needed it.

Modelled on `core/feed_health.py`, deliberately: same row dict, same fail-open
concurrent check, same save/load split, same ASCII render. Non-zero exit on
`ops signal-canary`. **Not** in `ops all-checks` — CI has no network (#663).
The overnight operator is what actually runs it.

Two properties make this safe to run unattended, and both are asserted in
`tests/test_signal_canary.py`:

**It cannot spend money.** Paid signals are skipped using `_APIFY_PAID_SIGNALS`
itself rather than a second hand-maintained list. Note the precise claim: zero
*dollars*, not zero *quota*. A measured probe run spent **~101 YouTube Data API
units** of the 10k/day allowance (`youtube` is free in dollars and metered in
units), so a nightly canary costs roughly 1% of a day's quota. Set
`CONTENT_SKIP_SIGNALS=youtube,youtube_comments` if that matters more than
knowing the search path is alive.

**It cannot trip the breaker.** It calls each signal function directly instead of
going through `register_signals._fetch_one`, which would both answer from the
shared cache and call `_record_signal_health` — persisting a trip to
`data/quota_state.json` via the quota governor, for up to a billing cycle.
A nightly canary that disabled a signal for the operator's next live run would
cause the outage it exists to prevent. Bypassing the cache is wanted for its own
sake too: a cache hit proves the cache is warm, not that the source is alive,
which is exactly how Tapology stayed "fine".
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from apis.signal_contract import (
    STATUS_AUTH,
    STATUS_ERROR,
    STATUS_HTTP,
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    STATUS_QUOTA,
    STATUS_RATE_LIMIT,
    STATUS_UNAVAILABLE,
    STATUS_UPSTREAM,
    normalize_signal,
)
from core.logging import get_logger

logger = get_logger("core.signal_canary")

_MAX_WORKERS = 8
STATUS_SKIPPED_PAID = "skipped"

# The whole point of decision §18, applied to the canary itself: "no match for
# this topic" is a healthy source answering, and must not be reported as a dead
# one. A canary that cries wolf on every off-domain signal gets ignored, which is
# worse than not having it - the probe topic is a UFC string, so coingecko,
# igdb and tmdb *should* come back empty.
_ANSWERED = frozenset({STATUS_OK, STATUS_INACTIVE})

# Deliberately off or unconfigured. Reported so the operator can see it, but not
# a failure: `ops doctor` owns required-vs-optional keys, and a signal switched
# off on purpose is not a source that died.
_NOT_CONFIGURED = frozenset({STATUS_NO_KEY, STATUS_UNAVAILABLE})

# A source that could not answer. This is the set the canary exists to catch.
_FAILED = frozenset(
    {STATUS_QUOTA, STATUS_RATE_LIMIT, STATUS_AUTH, STATUS_UPSTREAM, STATUS_HTTP, STATUS_ERROR}
)

# Evergreen and deliberately dull: a probe topic that trends would be a moving
# target, and the canary asks "did the source answer", not "was the answer good".
PROBE_TOPIC = "ufc heavyweight title fight"


def _paid_signals() -> frozenset[str]:
    """The authoritative paid set, read from the module that enforces it."""
    try:
        from apis.register_signals import _APIFY_PAID_SIGNALS

        return frozenset(_APIFY_PAID_SIGNALS)
    except Exception as exc:  # pragma: no cover - import guard only
        logger.warning("Could not read the paid-signal set (%s) - skipping none", exc)
        return frozenset()


def check_signal(name: str, func: Callable[[str], Any], *, topic: str = PROBE_TOPIC) -> dict:
    """Probe one signal. Never raises."""
    row: dict[str, Any] = {
        "name": name,
        # STATUS_ERROR, not a bare "dead" literal: `warnings` classifies on the
        # signal-contract vocabulary, so a raising signal has to speak it too.
        "status": STATUS_ERROR,
        "connected": False,
        "active": False,
        "detail": "",
    }
    if name in _paid_signals():
        row["status"] = STATUS_SKIPPED_PAID
        row["detail"] = "paid signal - not probed"
        return row
    try:
        signal = normalize_signal(func(topic))
        row["status"] = str(signal.get("status") or STATUS_ERROR)
        row["connected"] = bool(signal.get("connected"))
        row["active"] = bool(signal.get("active"))
        row["detail"] = str(signal.get("status_detail") or "")
    except Exception as exc:
        row["detail"] = f"{type(exc).__name__}: {exc}"
    return row


def check_signals(
    registry: dict[str, Callable[[str], Any]] | None = None, *, topic: str = PROBE_TOPIC
) -> list[dict]:
    """Probe every registered signal concurrently. Fail-open: [] on any error."""
    try:
        targets = registry if registry is not None else _registered()
        if not targets:
            return []
        items = sorted(targets.items())
        with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(items))) as pool:
            return list(pool.map(lambda kv: check_signal(kv[0], kv[1], topic=topic), items))
    except Exception as exc:
        logger.debug("signal canary failed: %s", exc)
        return []


def _registered() -> dict[str, Callable[[str], Any]]:
    from apis.signals_bootstrap import get_signal_registry

    return dict(get_signal_registry().get_registered_signals())


def _mark(status: str) -> str:
    if status == STATUS_SKIPPED_PAID:
        return "skip"
    if status == STATUS_OK:
        return "ok  "
    if status == STATUS_INACTIVE:
        return "none"  # answered, nothing matched this probe topic
    if status in _NOT_CONFIGURED:
        return "off "
    return "DEAD"


def warnings(rows: list[dict]) -> list[str]:
    """One line per signal that could not answer.

    Only `_FAILED` statuses count. An empty answer, a deliberately-off source and
    a paid signal we declined to probe are all reported by `render` and none of
    them is a warning.
    """
    out: list[str] = []
    for row in rows or []:
        if str(row.get("status")) not in _FAILED:
            continue
        detail = row.get("detail") or row.get("status") or "no detail"
        out.append(f"{row.get('name')}: {detail}")
    return out


def render(rows: list[dict]) -> str:
    """ASCII report (cp1252-safe, candidate 250)."""
    if not rows:
        return "Signal canary: no signals probed."
    lines = [f"Signal canary - {len(rows)} signal(s), probe topic {PROBE_TOPIC!r}", ""]
    for row in rows:
        detail = f"  {row['detail']}" if row.get("detail") else ""
        lines.append(f"  {_mark(str(row.get('status')))}  {row.get('name')!s:<22}{detail}")
    bad = warnings(rows)
    answered = sum(1 for r in rows if str(r.get("status")) in _ANSWERED)
    lines.append("")
    lines.append(
        f"{len(bad)} signal(s) could not answer." if bad else f"{answered} answered, none broken."
    )
    return "\n".join(lines)


def save_results(rows: list[dict]) -> None:
    """Persist for the reliability dashboard to read without touching the network."""
    try:
        import json
        import os

        from config.paths import SIGNAL_CANARY_FILE

        os.makedirs(os.path.dirname(SIGNAL_CANARY_FILE), exist_ok=True)
        payload = {"checked_at": datetime.now(timezone.utc).isoformat(), "results": rows}
        with open(SIGNAL_CANARY_FILE, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    except Exception as exc:
        logger.debug("signal canary results not saved: %s", exc)


def main() -> int:
    rows = check_signals()
    save_results(rows)
    print(render(rows))
    return 1 if warnings(rows) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
