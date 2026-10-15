"""Per-platform Buffer metrics, stored beside performance memory (#1195).

One ``posts`` query per Buffer channel, at most once a day. A post with no
``metricsUpdatedAt`` is unmeasured: its views are not stored as zero.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("publishing.platform_metrics")

METRICS_TEMPLATE = os.path.join(DATA_DIR, "platform_metrics_{channel}.json")


def _path(channel_id: str) -> str:
    return METRICS_TEMPLATE.format(channel=channel_id)


def load(channel_id: str) -> dict[str, Any]:
    try:
        with open(_path(channel_id), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(channel_id: str, data: dict[str, Any]) -> None:
    path = _path(channel_id)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp, path)


def get_row(channel_id: str, run_id: str, platform: str) -> dict[str, Any] | None:
    row = ((load(channel_id).get("rows") or {}).get(str(run_id)) or {}).get(platform)
    return row if isinstance(row, dict) else None


def refresh(
    channel_id: str,
    *,
    post: Any = None,
    now: datetime | None = None,
) -> list[str]:
    """Ask Buffer once per channel. Returns no lines; status reads the store.

    Quiet when Buffer is not configured. A failed query is not marked done, so
    the next run tries again, and it logs a warning because that day's numbers
    were not read.
    """
    from publishing import buffer_api, crosspost

    if post is None and not buffer_api.configured():
        return []
    moment = now or datetime.now(timezone.utc)
    day = moment.date().isoformat()
    store = load(channel_id)
    if store.get("fetched_on") == day:
        return []
    data = crosspost._load(channel_id)
    org = str((data.get("buffer") or {}).get("organization_id") or "")
    ids = crosspost.buffer_channel_ids(channel_id)
    if not org or not ids:
        return []
    rows = store.setdefault("rows", {})
    if not isinstance(rows, dict):
        rows = {}
        store["rows"] = rows
    kw: dict[str, Any] = {"post": post} if post is not None else {}
    posts = data.get("posts") or {}
    for service, buffer_id in ids.items():
        try:
            nodes = buffer_api.channel_post_metrics(org, buffer_id, **kw)
        except buffer_api.BufferError as exc:
            logger.warning("platform metrics %s: %s", service, exc.kind)
            return []
        except Exception as exc:
            logger.warning("platform metrics %s: %s", service, type(exc).__name__)
            return []
        by_id = {str(node.get("id") or ""): node for node in nodes}
        if not isinstance(posts, dict):
            continue
        for rid, entry in posts.items():
            if not isinstance(entry, dict):
                continue
            state = entry.get(service)
            if not isinstance(state, dict):
                continue
            node = by_id.get(str(state.get("post_id") or ""))
            if node is None:
                continue
            slot = rows.setdefault(str(rid), {})
            if isinstance(slot, dict):
                slot[service] = {key: value for key, value in node.items() if key != "id"}
    store["fetched_on"] = day
    _save(channel_id, store)
    return []
