"""Background clip anti-repeat (morning candidate).

Variation guard historically compared scripts, not pictures. This remembers
recent local clip paths in-process (and optionally a sidecar when CLIP_MEMORY
is on). Fail-open: if every candidate was used, pick anyway.
"""

from __future__ import annotations

import json
import os
import random
from collections import deque
from typing import Iterable

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("assets.clip_memory")

_recent: deque[str] = deque(maxlen=8)
CLIP_MEMORY_FILE = os.path.join(DATA_DIR, "clip_memory.json")


def _persist_on() -> bool:
    return os.getenv("CLIP_MEMORY", "").strip().lower() in ("1", "true", "yes", "on")


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def recent() -> list[str]:
    items = list(_recent)
    if not _persist_on():
        return items
    try:
        with open(CLIP_MEMORY_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        extra = data.get("paths") if isinstance(data, dict) else None
        if isinstance(extra, list):
            for p in extra:
                n = _norm(str(p))
                if n not in items:
                    items.append(n)
    except Exception as exc:
        logger.debug("clip memory read skipped: %s", exc)
    return items


def record(path: str) -> None:
    if not path:
        return
    n = _norm(path)
    _recent.append(n)
    if not _persist_on():
        return
    try:
        os.makedirs(os.path.dirname(CLIP_MEMORY_FILE) or ".", exist_ok=True)
        payload = {"paths": recent()[-8:]}
        tmp = CLIP_MEMORY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, CLIP_MEMORY_FILE)
    except Exception as exc:
        logger.debug("clip memory write skipped: %s", exc)


def reset() -> None:
    _recent.clear()


def pick_unseen(candidates: Iterable[str], *, rng: random.Random | None = None) -> str | None:
    paths = [p for p in candidates if p]
    if not paths:
        return None
    used = {_norm(p) for p in recent()}
    fresh = [p for p in paths if _norm(p) not in used]
    pool = fresh or paths  # fail-open: repeat rather than render without a clip
    choice = (rng or random).choice(pool)
    record(choice)
    return choice
