"""What the last seven days cost (#776).

Long-form voice went back to ElevenLabs on 2026-09-17 (#775), so spend can climb again
without anything saying so until the monthly bill. Every run already writes
`data/traces/<id>.json` with `at` (epoch) and `cost.total`, so the rolling number needs no
new store. Warn only - the operator asked for a number, not a block.

    SPEND_WARN_WEEKLY_USD=5.00   # 0/off silences the line
"""

from __future__ import annotations

import json
import os
import time

from config.paths import TRACES_DIR
from core.logging import get_logger

logger = get_logger("core.spend_week")

WINDOW_DAYS = 7
_DEFAULT_WARN_USD = 5.00


def warn_threshold() -> float:
    """0.0 means "never warn"."""
    raw = (os.getenv("SPEND_WARN_WEEKLY_USD", "") or "").strip().lower()
    if raw in ("0", "off", "false", "no", "none"):
        return 0.0
    try:
        return float(raw) if raw else _DEFAULT_WARN_USD
    except ValueError:
        return _DEFAULT_WARN_USD


def weekly_spend(*, days: int = WINDOW_DAYS, now: float | None = None) -> tuple[float, int]:
    """(usd, runs) spent inside the window. Unreadable traces are skipped, never raised."""
    cutoff = (now or time.time()) - max(1, int(days)) * 86400
    total = 0.0
    runs = 0
    try:
        names = os.listdir(TRACES_DIR)
    except OSError:
        return 0.0, 0
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(TRACES_DIR, name), encoding="utf-8") as f:
                trace = json.load(f)
            at = float(trace.get("at") or 0.0)
            cost = float((trace.get("cost") or {}).get("total") or 0.0)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            logger.debug("trace %s unreadable for weekly spend: %s", name, exc)
            continue
        if at >= cutoff and cost > 0:
            total += cost
            runs += 1
    return round(total, 4), runs


def spend_warning_line(*, days: int = WINDOW_DAYS, now: float | None = None) -> str:
    """The over-the-line warning, or "" when under it (or switched off)."""
    threshold = warn_threshold()
    if threshold <= 0:
        return ""
    usd, runs = weekly_spend(days=days, now=now)
    if usd <= threshold:
        return ""
    return (
        f"Spend: ${usd:,.2f} in {days} days over the ${threshold:,.2f} warn line "
        f"({runs} run{'s' if runs != 1 else ''}) - py -m scripts.ops cost-tower"
    )
