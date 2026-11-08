"""#1828 (B10.7, wave 160): a per-video bridge card at 7 days.

Each video published 7-14 days ago, on one line, in the bridge's own terms: organic views in its
first week, the share who stayed, the subscribers it brought, its watch hours (a long video's are
the YPP hours), and what its run cost. In the weekly report, most-viewed first.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.success.video_card")

CARD_MAX = 12


def _number(metrics: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _run_features(run_id: int) -> dict[str, Any]:
    from storage.repositories.content_runs import get_content_run_repository

    run = get_content_run_repository().get(run_id) if run_id else None
    try:
        data = json.loads(getattr(run, "features_json", "") or "{}") if run else {}
    except (TypeError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    if run is not None and getattr(run, "title", None):
        data.setdefault("title", str(run.title))
    return data


def video_cards(
    channel_id: str,
    *,
    today: date | None = None,
    rows: list[Any] | None = None,
    features: Callable[[int], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """{run_id, title, long, organic7, stayed, subs, hours, cost} for each public video published
    7-14 days ago with its first week measured."""
    from core.success.target import views_7d

    day = today or date.today()
    read = features or _run_features
    if rows is None:
        from storage.repositories.publish_log import get_publish_log_repository, is_seeded

        rows = [r for r in get_publish_log_repository().list_uploaded_for_channel(channel_id)
                or [] if not is_seeded(r)]  # fmt: skip
    start = datetime.combine(day - timedelta(days=14), datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(day - timedelta(days=7), datetime.max.time(), tzinfo=timezone.utc)
    cards: list[dict[str, Any]] = []
    for row in rows:
        when = getattr(row, "published_at", None)
        if not isinstance(when, datetime):
            continue
        when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        if not start <= when <= end or str(getattr(row, "privacy_status", "")).lower() != "public":
            continue
        try:
            metrics = json.loads(getattr(row, "metrics_json", "") or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(metrics, dict):
            continue
        week = views_7d(metrics, when)
        if week is None:
            continue
        run_id = int(getattr(row, "content_run_id", 0) or 0)
        feats = read(run_id)
        cost = (
            (feats.get("cost") or {}).get("total") if isinstance(feats.get("cost"), dict) else None
        )
        stayed = metrics.get("stayed_share")
        cards.append({
            "run_id": run_id,
            "title": str(feats.get("title") or f"run {run_id}"),
            "long": bool(feats.get("long_form") or feats.get("compilation")),
            "organic7": int(week),  # views_7d takes the paid days out (#954)
            "stayed": float(stayed) if isinstance(stayed, (int, float)) else None,
            "subs": int(_number(metrics, "subscribers_gained")),
            "hours": round(_number(metrics, "estimated_minutes_watched") / 60.0, 1),
            "cost": float(cost) if isinstance(cost, (int, float)) else None,
        })  # fmt: skip
    return sorted(cards, key=lambda c: -c["organic7"])


def card_line(card: dict[str, Any]) -> str:
    stayed = f"stayed {card['stayed']:.0%}" if card.get("stayed") is not None else "stayed n/a"
    cost = f"${card['cost']:.2f}" if card.get("cost") is not None else "cost n/a"
    kind = "long" if card.get("long") else "Short"
    # a Short's watch time is not the YPP hours - shown for a long video only
    hours = f" · {card['hours']:g} hours" if card.get("long") else ""
    return (f"  run {card['run_id']} ({kind}) {str(card['title'])[:48]}: {card['organic7']:,} "
            f"organic views · {stayed} · +{card['subs']} subscribers{hours} · {cost}")  # fmt: skip


def video_card_lines(channel_id: str, **kwargs: Any) -> list[str]:
    """The weekly report's cards; [] when no video turned 7 days old this week. Never raises."""
    try:
        cards = video_cards(channel_id, **kwargs)
    except Exception as exc:
        logger.debug("video cards skipped: %s", exc)
        return []
    if not cards:
        return []
    shown = cards[:CARD_MAX]
    more = f" (top {CARD_MAX} of {len(cards)})" if len(cards) > CARD_MAX else ""
    return [f"Each video at 7 days (#1828, published 7-14 days ago){more}:",
            *(card_line(c) for c in shown)]  # fmt: skip
