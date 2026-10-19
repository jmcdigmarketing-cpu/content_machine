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
    if not isinstance(data, dict):
        return {}
    for platforms in (data.get("rows") or {}).values():
        for row in (platforms or {}).values() if isinstance(platforms, dict) else ():
            _remap(row)
    return data


def _remap(row: Any) -> None:
    """Wave 113: a measured row stored before TikTok's "Video Views" was mapped is read again
    from its raw `buffer` metrics, so it does not wait for the next day's fetch."""
    if not isinstance(row, dict) or not row.get("measured"):
        return
    from publishing.buffer_api import map_metrics

    for key, value in map_metrics(row.get("buffer") or {}).items():
        if row.get(key) is None:
            row[key] = value


def _save(channel_id: str, data: dict[str, Any]) -> None:
    path = _path(channel_id)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp, path)


def get_row(channel_id: str, run_id: str, platform: str) -> dict[str, Any] | None:
    row = ((load(channel_id).get("rows") or {}).get(str(run_id)) or {}).get(platform)
    return row if isinstance(row, dict) else None  # load() has remapped it


def _utc_hour(stamp: Any) -> int | None:
    if not stamp:
        return None
    text = str(stamp).replace("Z", "+00:00")
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).hour


def _length_choice(run: Any) -> str:
    try:
        timings = json.loads(getattr(run, "timings_json", "") or "{}")
    except (TypeError, ValueError):
        return ""
    if not isinstance(timings, dict):
        return ""
    choice = str(timings.get("length_preset") or "")
    return choice if choice in {"1", "2", "3", "4"} else ""


def _stored_metrics(node: dict[str, Any], state: dict[str, Any], run_id: str) -> dict[str, Any]:
    """The metric row plus the hour, domain and length the recommender reads."""
    from publishing import crosspost

    stored = {key: value for key, value in node.items() if key != "id"}
    hour = _utc_hour(state.get("sent_at") or state.get("due_at"))
    if hour is not None:
        stored["hour"] = hour
    run = None
    try:
        run = crosspost._content_run(int(run_id))
    except (TypeError, ValueError):
        run = None
    except Exception as exc:
        logger.debug("platform metrics run %s: %s", run_id, type(exc).__name__)
        run = None
    if run is None:
        return stored
    domain = str(getattr(run, "domain", "") or "").strip()
    if not domain:
        from core.run_features import run_domain

        try:
            domain = run_domain(int(run_id))
        except (TypeError, ValueError):
            domain = ""
    if domain:
        stored["domain"] = domain
    length = _length_choice(run)
    if length:
        stored["length"] = length
    return stored


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
                slot[service] = _stored_metrics(node, state, str(rid))
    store["fetched_on"] = day
    _save(channel_id, store)
    return []
