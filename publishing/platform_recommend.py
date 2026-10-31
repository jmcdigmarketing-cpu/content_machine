"""Per-platform domain, length and post hour (#1196).

Samples are the measured rows in the platform metrics store. A bucket - an hour, a domain, a
length - is a candidate only with ``MODERATE_SAMPLES`` (4) posts of its own (#1774, decision
89): Instagram's hour had been 8 PM on 2 posts against 21 at 10 PM. With no candidate the post
time stays the 10 PM evening slot (decision 64). Hours are the channel's local hours, read from
when each post went out, so the clock change does not move them.
"""

from __future__ import annotations

from typing import Any

from core.recommender_confidence import MODERATE_SAMPLES, shrunk_mean

_LABEL = {"tiktok": "TikTok", "instagram": "Instagram"}


def _measured(channel_id: str, platform: str) -> list[dict[str, Any]]:
    """Measured rows, each with `local_hour` when its post's time is known."""
    from publishing import crosspost
    from publishing.platform_metrics import load

    rows = load(channel_id).get("rows") or {}
    if not isinstance(rows, dict):
        return []
    posts = crosspost._load(channel_id).get("posts") or {}
    zone = crosspost._zone(channel_id)
    out: list[dict[str, Any]] = []
    for run_id, platforms in rows.items():
        if not isinstance(platforms, dict):
            continue
        row = platforms.get(platform)
        if isinstance(row, dict) and row.get("measured") and row.get("views") is not None:
            entry = posts.get(str(run_id)) if isinstance(posts, dict) else None
            state = entry.get(platform) if isinstance(entry, dict) else None
            stamp = (state or {}).get("sent_at") or (state or {}).get("due_at")
            when = crosspost._stamp(str(stamp).replace("Z", "+00:00")) if stamp else None
            local = {"local_hour": when.astimezone(zone).hour} if when is not None else {}
            out.append({**row, **local})
    return out


def _best(rows: list[dict[str, Any]], field: str, *, own: int = MODERATE_SAMPLES) -> Any:
    """The bucket with the best shrunk mean of views among those with `own` posts of their own;
    None when none has that many."""
    grouped: dict[Any, list[float]] = {}
    for row in rows:
        bucket = row.get(field)
        if bucket is None:
            continue
        grouped.setdefault(bucket, []).append(float(row["views"]))
    flat = [value for values in grouped.values() for value in values]
    candidates = [bucket for bucket, values in grouped.items() if len(values) >= own]
    if not candidates:
        return None
    prior = sum(flat) / len(flat)
    return max(candidates, key=lambda bucket: shrunk_mean(grouped[bucket], prior))


def hour_choice(channel_id: str, platform: str) -> tuple[int | None, str]:
    """(the channel's local hour, note). None while no hour has posts enough of its own."""
    rows = [row for row in _measured(channel_id, platform) if row.get("local_hour") is not None]
    label = _LABEL.get(platform, platform.capitalize())
    best = _best(rows, "local_hour")
    if best is None:
        return None, (
            f"{label}: no hour has {MODERATE_SAMPLES} posts of its own yet ({len(rows)} samples)"
        )
    hour = int(best)
    return hour, f"{label}'s hour {hour:02d}:00 local ({len(rows)} samples)"


def learning_line(channel_id: str, platform: str) -> str:
    """Domain, length and hour for one feed. Empty when that feed has no rows."""
    rows = _measured(channel_id, platform)
    if not rows:
        return ""
    label = _LABEL.get(platform, platform.capitalize())
    if len(rows) < MODERATE_SAMPLES:
        return (  # decision 64: the hour is the 10 PM evening slot, not YouTube's
            f"{label} uses the 10 PM slot and YouTube's domain and length "
            f"({len(rows)} samples, need {MODERATE_SAMPLES})"
        )
    picks = {field: _best(rows, field) for field in ("local_hour", "domain", "length")}
    shown = ", ".join(
        f"{name} {'none with 4 posts yet' if picks[field] is None else picks[field]}"
        for name, field in (("hour", "local_hour"), ("domain", "domain"), ("length", "length"))
    )
    return f"{label}'s own picks ({len(rows)} samples): {shown}"


def feed_lines(channel_id: str) -> list[str]:
    """Views, the best video, and what that feed preferred. Empty store says so."""
    from publishing import crosspost
    from publishing.platform_metrics import load

    rows = load(channel_id).get("rows") or {}
    if not isinstance(rows, dict) or not rows:
        return ["No platform results yet."]
    posts = crosspost._load(channel_id).get("posts") or {}
    if not isinstance(posts, dict):
        posts = {}
    lines: list[str] = []
    for platform, label in _LABEL.items():
        total = 0
        measured = 0
        best_views = -1
        best_title = ""
        for rid, platforms in rows.items():
            row = platforms.get(platform) if isinstance(platforms, dict) else None
            if not isinstance(row, dict) or not row.get("measured") or row.get("views") is None:
                continue
            views = int(row["views"])
            measured += 1
            total += views
            if views > best_views:
                best_views = views
                entry = posts.get(str(rid))
                if isinstance(entry, dict) and entry.get("title"):
                    best_title = str(entry["title"])
                else:
                    best_title = str(rid)
        if not measured:
            lines.append(f"{label}: not measured yet")
            continue
        lines.append(
            f"{label}: {total} views, best {best_title} ({best_views} views).{_watch_note(rows, platform, channel_id)} "
            f"{learning_line(channel_id, platform)}"
        )
    return lines or ["No platform results yet."]


def _intro_seconds(channel_id: str) -> float:
    from video.intro_offset import intro_offset_seconds

    return intro_offset_seconds(channel_id)


def _watch_note(rows: dict[str, Any], platform: str, channel_id: str) -> str:
    """Wave 113: TikTok's viewers watched 1.24-1.68 s on average - inside the 2.15 s intro."""
    watched = [
        float(row["avg_watch_s"])
        for platforms in rows.values()
        if isinstance(platforms, dict)
        for row in [platforms.get(platform)]
        if isinstance(row, dict) and row.get("views") and row.get("avg_watch_s") is not None
    ]
    if not watched:
        return ""
    mean = sum(watched) / len(watched)
    note = f" Viewers watch {mean:.1f} s on average"
    intro = _intro_seconds(channel_id)
    if intro and mean < intro:
        note += f" - less than the {intro:.2f} s intro"
    return note + "."
