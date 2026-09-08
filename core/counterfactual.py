"""#358: persist the recommendation that was ignored. Fail-open JSON."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.counterfactual")

STORE_NAME = "counterfactual.json"
STORE_PATH = os.path.join(DATA_DIR, STORE_NAME)


def default_path() -> str:
    return str(STORE_PATH)


def record_override(
    offered: str,
    chosen: str,
    *,
    path: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    row = {
        "offered": offered,
        "chosen": chosen,
        "reason": reason,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    target = path or default_path()
    try:
        rows: list[Any] = []
        if os.path.isfile(target):
            with open(target, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, list):
                rows = loaded
        rows.append(row)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2)
    except Exception as exc:
        logger.debug("counterfactual log skipped: %s", exc)
    return row
