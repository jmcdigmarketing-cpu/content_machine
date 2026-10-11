"""One probe that says the internet is down (#393).

When the connection drops, every signal fails on its own - seven "unavailable" lines, seven
incidents in the ledger - and the operator starts debugging seven integrations. This module
reads the failures as one thing: enough signals failing *to connect* in the same run is a
network problem, and one request to a host that is always up confirms it.

Nothing here runs inside the signal pool, changes a signal's result or touches a breaker:
it reads finished results. The probe is one HEAD request, made only when the failures already
look like a dead connection.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from core.logging import get_logger

logger = get_logger("apis.net_probe")

PROBE_URL = "https://www.gstatic.com/generate_204"
MIN_FAILED = 4

# What a request that never reached the host says, across requests / urllib3 / socket.
_CONNECTION = re.compile(
    r"connection|getaddrinfo|name resolution|name or service|max retries|"
    r"timed out|timeout|unreachable|failed to establish|\bdns\b",
    re.IGNORECASE,
)


def failed_to_connect(signals: dict[str, Any] | None) -> list[str]:
    """Signals whose failure reads as never reaching the host, by name."""
    out: list[str] = []
    for name, sig in (signals or {}).items():
        if not isinstance(sig, dict) or sig.get("connected"):
            continue
        detail = f"{sig.get('status_detail') or ''} {sig.get('status') or ''}"
        if _CONNECTION.search(detail):
            out.append(str(name))
    return sorted(out)


def looks_offline(signals: dict[str, Any] | None, *, minimum: int = MIN_FAILED) -> list[str]:
    """The signals that could not connect, when there are enough of them to be the network:
    at least `minimum`, and at least half of everything that ran. Otherwise []."""
    names = failed_to_connect(signals)
    ran = sum(1 for sig in (signals or {}).values() if isinstance(sig, dict))
    if len(names) >= minimum and len(names) * 2 >= ran:
        return names
    return []


def online(timeout: float = 2.0) -> bool:
    """One request to a host that is always up. False on any failure."""
    try:
        import requests

        requests.head(PROBE_URL, timeout=timeout)
        return True
    except Exception as exc:
        logger.debug("network probe failed: %s", exc)
        return False


def offline_line(signals: dict[str, Any] | None, *, probe: Callable[[], bool] | None = None) -> str:
    """One line for the operator, or "" - asked only when the failures already look like it."""
    names = looks_offline(signals)
    if not names:
        return ""
    if (probe or online)():
        return ""
    shown = ", ".join(names[:4]) + ("..." if len(names) > 4 else "")
    return (
        f"The internet looks down: {len(names)} signals could not connect ({shown}). "
        "Nothing is wrong with them - check the connection and run again."
    )
