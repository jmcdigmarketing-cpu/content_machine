"""#1719 (B05.23, wave 160): the follow line's wording on trial, Nov 8-21.

A Short with no reason of its own to follow (not a countdown, a series, a debate or a part) ends
on the Week in Review's weekly time (#1943, arm "weekly"). The other arm promises what the
channel description does: the next big story lands here first (arm "first"). Drafts alternate,
the arm with fewer goes next; the weekly report reads first-week subscribers per Short by arm.
`FOLLOW_TRIAL=false` stops it (the suite does).
"""

from __future__ import annotations

import os
import statistics
from collections.abc import Callable
from datetime import date
from typing import Any

from core.logging import get_logger

logger = get_logger("core.success.follow_trial")

FOLLOW_LEVER = "follow_line"
FOLLOW_TRIAL = ("2026-11-08", "2026-11-21")
FOLLOW_ARMS = ("weekly", "first")
_LEAD = " End on why to follow, in your own words, once:"


def enabled() -> bool:
    return os.getenv("FOLLOW_TRIAL", "true").strip().lower() not in ("0", "false", "no", "off")


def follow_arm(
    channel_id: str, *, today: date | None = None, rows: list[dict[str, Any]] | None = None
) -> str | None:
    """The arm for the next draft inside the trial - the one with fewer drafts - or None."""
    day = (today or date.today()).isoformat()
    if not enabled() or not FOLLOW_TRIAL[0] <= day <= FOLLOW_TRIAL[1]:
        return None
    try:
        if rows is None:
            from core.experiments import _assignments

            rows = list(_assignments(channel_id, FOLLOW_LEVER))
    except Exception as exc:
        logger.debug("follow arms unread: %s", exc)
        rows = []
    counts = {arm: sum(1 for r in rows or [] if r.get("arm") == arm) for arm in FOLLOW_ARMS}
    return min(FOLLOW_ARMS, key=lambda arm: counts[arm])


def follow_wording(arm: str | None, when: str) -> str:
    """The brief's last-line direction for a Short with no reason of its own to follow."""
    if arm == "first":
        return (f'{_LEAD} the next big story lands here first - for example "Follow so the next '
                'big story finds you first."')  # fmt: skip
    return (
        f"{_LEAD} {when} the week's Shorts come out as one video - for example "
        f'"Follow - the week\'s best lands {when}."'
    )


def follow_trial_lines(
    channel_id: str,
    *,
    today: date | None = None,
    rows: list[Any] | None = None,
    features: Callable[[int], dict[str, Any]] | None = None,
    arms: dict[int, str] | None = None,
) -> list[str]:
    """#1719's readout: each arm's median first-week subscribers and organic views per Short, or
    [] before a Short of each arm is measured."""
    try:
        if arms is None:
            from core.experiments import _assignments

            arms = {int(r.get("run_id") or 0): str(r.get("arm") or "")
                    for r in _assignments(channel_id, FOLLOW_LEVER)}  # fmt: skip
        if not arms:
            return []
        from core.success.formats import measured_shorts

        by_arm: dict[str, list[dict[str, Any]]] = {}
        for short in measured_shorts(channel_id, today=today, rows=rows, features=features):
            arm = arms.get(int(short.get("run_id") or 0))
            if arm:
                by_arm.setdefault(arm, []).append(short)
        if len(by_arm) < 2:
            return []
        parts = [
            f"{arm} {statistics.median(float(s.get('subs') or 0) for s in shorts):g} subscribers, "
            f"{statistics.median(float(s.get('views7') or 0) for s in shorts):g} views (n={len(shorts)})"
            for arm, shorts in sorted(by_arm.items())
        ]
        return ["Follow line (#1719, the Week in Review's time against 'the next big story here "
                "first'; median per Short, first week): " + " · ".join(parts)]  # fmt: skip
    except Exception as exc:
        logger.debug("follow trial lines skipped: %s", exc)
        return []
