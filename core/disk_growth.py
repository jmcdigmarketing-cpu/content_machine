"""#382 project days-until-full for output/ from recent growth."""

from __future__ import annotations

import os
import time
from pathlib import Path


def project_days_until_full(
    root: str | os.PathLike[str],
    *,
    free_bytes: int,
    now_ts: float | None = None,
) -> str:
    """Honest empty when the dir is new; never a WARNING."""
    base = Path(root)
    if not base.exists():
        return "empty — no growth to project"
    files = [p for p in base.rglob("*") if p.is_file()]
    if not files:
        return "empty — no growth to project"
    now = float(now_ts if now_ts is not None else time.time())
    stamped = []
    for path in files:
        try:
            stamped.append((path.stat().st_mtime, path.stat().st_size))
        except OSError:
            continue
    if len(stamped) < 2:
        return "empty — no growth to project"
    stamped.sort()
    first_t, _ = stamped[0]
    last_t = stamped[-1][0]
    elapsed = max(1.0, last_t - first_t)

    # Size at each end of the window: cumulative bytes of files whose mtime ≤ t.
    def _bytes_as_of(t: float) -> int:
        return sum(sz for mt, sz in stamped if mt <= t + 1e-9)

    grew = _bytes_as_of(last_t) - _bytes_as_of(first_t)
    if grew <= 0:
        return "no net growth in the recent window"
    rate_per_day = grew / (elapsed / 86400.0)
    if rate_per_day <= 0:
        return "no net growth in the recent window"
    days = max(0.0, float(free_bytes) / rate_per_day)
    _ = now  # reserved for tests that pass a frozen clock
    return f"~{days:.0f} days until full at recent growth"
