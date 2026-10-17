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


def arc_series_name(last_topic: str, family: str) -> str:
    """What the arc is about, from its last topic - never just the franchise label (#879).

    Run 99 continued "the UFC arc" as "UFC week 2": week 1 had no "week N", so the label
    replaced the topic and the Contender Series was lost. The longest name in the topic
    wins; a lower-case topic keeps its words; an empty one falls back to the label.
    """
    from apis.topic_tokens import title_phrases

    label = _label(family)
    text = (last_topic or "").strip()
    names = [
        p for p in title_phrases(text, max_words=5) if p.lower() not in (family, label.lower())
    ]
    if names:
        return max(names, key=len)
    base = text.split(":")[0].strip(" .,-!?")
    return base or label


def next_arc_topic(last_topic: str, ordinal: int, family: str) -> str:
    """The arc's next topic: what it is about, without the arc's counter (#1205).

    Run 153 (2026-10-15) was drafted from "Shavkat Rakhmonov week 4": the 4 counts the
    channel's UFC videos, and the angle and the script read it as the fighter's - "Shavkat
    Rakhmonov's week 4 performance", "So week four is progress without a finish line." The
    counter stays in the arc record and the best-bet line; `record_published_topic` moves it on
    from the record when a topic carries no week.
    """
    plain = re.sub(r"\s{2,}", " ", _WEEK_RE.sub("", last_topic or "")).strip(" -:,")
    return arc_series_name(plain, family)


def record_published_topic(channel_id: str, topic: str, *, video_id: str = "") -> None:
    """Remember the published franchise + ordinal. No-op without a franchise. ``video_id``
    (#1245) lets the follow-up wait until that video is public."""
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
        "video_id": str(video_id or ""),
    }
    _save(data)


def _stamp(value: Any) -> datetime | None:
    try:
        when = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _not_public(channel_id: str, video_id: str, updated_at: str = "") -> bool:
    """#1245: the arc's last video is on YouTube and not public. A row saved before the id was
    kept is matched to the upload logged within 10 minutes of it; a log that cannot be read is
    not held back."""
    saved = _stamp(updated_at) if not video_id else None
    if not video_id and saved is None:
        return False
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
            if video_id:
                found = str(getattr(row, "youtube_video_id", "") or "") == video_id
            else:
                logged = _stamp(getattr(row, "published_at", None))
                found = (
                    logged is not None
                    and saved is not None
                    and abs((logged - saved).total_seconds()) <= 600
                )
            if found:
                return str(getattr(row, "privacy_status", "") or "").lower() != "public"
    except Exception as exc:
        logger.debug("arc privacy unread for %s: %s", video_id or updated_at, exc)
    return False


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
        if _not_public(
            channel_id, str(row.get("video_id") or ""), str(row.get("updated_at") or "")
        ):
            # #1245: run 126 was uploaded unlisted at 7:07 PM and led the menu as "Ben Affleck".
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
        rationale=f"continue {topic} ({_label(family)} arc, video {ordinal} → {ordinal + 1})"
        + (f' - after "{last_topic[:70]}"' if last_topic else ""),
    )
