"""Franchise topic graph — continue week-1 → week-2 instead of replaying the same seed.

JSON sidecar (no new SQLite column). Fail-open: missing/corrupt file means today's
best-bet behaviour is unchanged. Recorded on a successful YouTube publish.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any

from core.channel_context import anchor_families
from core.logging import get_logger

logger = get_logger("core.topic_graph")

_WEEK_RE = re.compile(r"\bweek\s+(\d+)\b", re.I)
_LABELS = {
    "gta": "GTA",
    "ufc": "UFC",
    "marvel rivals": "Marvel Rivals",
    "call of duty": "Call of Duty",
}


def _path() -> str:
    from config.paths import TOPIC_GRAPH_FILE

    return TOPIC_GRAPH_FILE


def _load() -> dict[str, Any]:
    path = _path()
    if not os.path.exists(path):
        return {"channels": {}}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"channels": {}}
        data.setdefault("channels", {})
        return data
    except Exception as exc:
        logger.debug("topic graph read failed: %s", exc)
        return {"channels": {}}


def _save(data: dict[str, Any]) -> None:
    from config.paths import ensure_data_dir

    try:
        ensure_data_dir()
        path = _path()
        directory = os.path.dirname(path) or "."
        fd, tmp = tempfile.mkstemp(suffix=".tmp", prefix="topic_graph_", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:
        logger.debug("topic graph write skipped: %s", exc)


def _franchise(topic: str) -> str | None:
    families = anchor_families(topic)
    if not families:
        return None
    if "gta" in families:
        return "gta"
    return sorted(families)[0]


def _label(family: str) -> str:
    return _LABELS.get(family, family.title())


def _ordinal_from_topic(topic: str) -> int | None:
    m = _WEEK_RE.search(topic or "")
    if not m:
        return None
    try:
        return max(1, int(m.group(1)))
    except ValueError:
        return None


def next_arc_topic(last_topic: str, ordinal: int, family: str) -> str:
    nxt = ordinal + 1
    if _WEEK_RE.search(last_topic or ""):
        return _WEEK_RE.sub(f"week {nxt}", last_topic, count=1)
    return f"{_label(family)} week {nxt}"


def record_published_topic(channel_id: str, topic: str) -> None:
    """Remember the published franchise + ordinal. No-op without a franchise."""
    family = _franchise(topic)
    if not family:
        return
    ordinal = _ordinal_from_topic(topic) or 1
    data = _load()
    ch = data.setdefault("channels", {}).setdefault(channel_id, {})
    arcs = ch.setdefault("arcs", {})
    prev = arcs.get(family) or {}
    if isinstance(prev, dict) and _ordinal_from_topic(topic) is None:
        try:
            ordinal = int(prev.get("ordinal") or 0) + 1
        except (TypeError, ValueError):
            ordinal = 1
    arcs[family] = {
        "ordinal": ordinal,
        "last_topic": topic,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _save(data)


def follow_up_seed(channel_id: str):
    """BestBetResult for the next ordinal on the latest arc, or None."""
    from core.best_bet import BestBetResult
    from core.engagement import safe_infer_domain

    data = _load()
    arcs = ((data.get("channels") or {}).get(channel_id) or {}).get("arcs") or {}
    if not isinstance(arcs, dict) or not arcs:
        return None
    latest: tuple[str, dict] | None = None
    for family, row in arcs.items():
        if not isinstance(row, dict):
            continue
        stamp = str(row.get("updated_at") or "")
        if latest is None or stamp >= str(latest[1].get("updated_at") or ""):
            latest = (family, row)
    if latest is None:
        return None
    family, row = latest
    try:
        ordinal = int(row.get("ordinal") or 1)
    except (TypeError, ValueError):
        ordinal = 1
    last_topic = str(row.get("last_topic") or "")
    topic = next_arc_topic(last_topic, ordinal, family)
    if not topic.strip():
        return None
    return BestBetResult(
        topic=topic,
        domain=safe_infer_domain(topic, channel_id),
        avg_engaged_rate=0.0,
        source="arc",
        supporting_runs=1,
        rationale=f"continue the {_label(family)} arc (week {ordinal} → week {ordinal + 1})",
    )
