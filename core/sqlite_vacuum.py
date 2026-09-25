"""#688: reclaim sqlite pages on a path the caller names. Never assume the operator DB."""

from __future__ import annotations

import os
import sqlite3
from typing import Any


def vacuum_sqlite(path: str) -> dict[str, Any]:
    """VACUUM `path` and return before/after sizes. Caller chooses the file."""
    target = os.path.abspath(path)
    if not os.path.isfile(target):
        raise FileNotFoundError(target)
    before = os.path.getsize(target)
    conn = sqlite3.connect(target)
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()
    after = os.path.getsize(target)
    return {"path": target, "before": before, "after": after}
