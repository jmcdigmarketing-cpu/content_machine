"""#83 (the operator, 2026-10-18: "yes, 1 in 5"): holdout drafts, so the ranking can be checked.

The idea ranking's composite has never predicted engagement (r=-0.15, #819), and a learning
loop that only ever takes its own top pick cannot tell a good ranking from a lucky one. Every
`HOLDOUT_EVERY`th overnight draft (5; 0 switches it off - the suite does) takes another of the
top ten at random instead of the top one, and its pick record says `holdout: true`. `ops
predictions` then compares what holdouts held with what the ranked overnight picks held.
"""

from __future__ import annotations

import json
import os
import random
import threading
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.predictions.holdouts")

HOLDOUT_FILE = os.path.join(DATA_DIR, "holdouts.json")
_LOCK = threading.Lock()
_MIN_EACH = 5  # measured videos on each side before the comparison is read as anything


def every() -> int:
    try:
        return max(0, int(os.getenv("HOLDOUT_EVERY", "5") or 0))
    except ValueError:
        return 5


def _load() -> dict[str, Any]:
    try:
        with open(HOLDOUT_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def next_slots(count: int) -> list[bool]:
    """Which of the next `count` overnight drafts are holdouts - every Nth draft counted across
    nights - and the count moved on."""
    n = every()
    if not n:
        return [False] * max(0, count)
    with _LOCK:
        state = _load()
        done = int(state.get("drafts") or 0)
        slots = [bool(n) and (done + i + 1) % n == 0 for i in range(max(0, count))]
        state["drafts"] = done + max(0, count)
        try:
            os.makedirs(os.path.dirname(HOLDOUT_FILE) or ".", exist_ok=True)
            with open(HOLDOUT_FILE, "w", encoding="utf-8") as handle:
                json.dump(state, handle)
        except OSError as exc:
            logger.debug("holdout count not saved: %s", exc)
    return slots


def holdout_choice(candidates: list[Any], taken: set[str], *, seed: str) -> Any | None:
    """A pick the ranking would not have made: one of the top ten after the first, not taken."""
    pool = [c for c in candidates[1:10] if getattr(c, "topic", None) not in taken]
    if not pool:
        return None
    return random.Random(seed).choice(pool)


def _batch_runs(channel_id: str) -> dict[int, bool]:
    """{run_id: holdout?} for every run an overnight batch picked."""
    from storage.repositories.content_runs import get_content_run_repository

    out: dict[int, bool] = {}
    for run in get_content_run_repository().list_for_channel(channel_id):
        try:
            features = json.loads(getattr(run, "features_json", None) or "{}")
        except (TypeError, ValueError):
            continue
        pick = features.get("best_bet") if isinstance(features, dict) else None
        if isinstance(pick, dict) and str(pick.get("by") or "") == "batch":
            out[int(run.id)] = bool(pick.get("holdout"))
    return out


def holdout_line(channel_id: str) -> str:
    """ "Holdouts: 2 measured, 31% engaged; ranked overnight picks: 6 measured, 28%", or ""."""
    from core.engagement_predictor import run_engagement_map

    try:
        runs = _batch_runs(channel_id)
        rates = run_engagement_map(channel_id)
    except Exception as exc:
        logger.debug("holdout line skipped: %s", exc)
        return ""
    held = [float(rates[r]) for r, hold in runs.items() if hold and r in rates]
    ranked = [float(rates[r]) for r, hold in runs.items() if not hold and r in rates]
    drafted = sum(1 for hold in runs.values() if hold)
    if not drafted and not held:
        return f"Holdouts: none yet - every {every()}th overnight draft is one" if every() else ""

    def side(rows: list[float]) -> str:
        if not rows:
            return "0 measured"
        return f"{len(rows)} measured, {sum(rows) / len(rows):.0%} engaged"

    note = "" if min(len(held), len(ranked)) >= _MIN_EACH else f" - read it at {_MIN_EACH} each"
    return (
        f"Holdouts: {side(held)} ({drafted} drafted); ranked overnight picks: {side(ranked)}{note}"
    )
