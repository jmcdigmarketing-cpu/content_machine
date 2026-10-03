"""
Sync YouTube Analytics for uploaded videos in publish_log.

Usage:
    py -m analytics.sync_metrics --channel tapin
"""

from __future__ import annotations

import argparse

from analytics.youtube_metrics import _analytics_enabled, refresh_publish_metrics
from config.channels import resolve_channel_id
from storage.repositories.publish_log import get_publish_log_repository


def _probe_analytics_api(channel_id: str) -> tuple[bool, str]:
    """
    Make a single test query to detect common setup errors before iterating all videos.
    Returns (ok, error_message).
    """
    try:
        from youtube.oauth import get_youtube_analytics_service

        service = get_youtube_analytics_service(channel_id)
        if not service:
            return (
                False,
                "OAuth token missing — run: py -m youtube.oauth_setup --channel " + channel_id,
            )
        from datetime import date, timedelta

        end = date.today().isoformat()
        start = (date.today() - timedelta(days=7)).isoformat()
        # Channel-level query (no dimensions) — the simplest shape that validates
        # both that the API is enabled and the token scope is present.
        service.reports().query(
            ids="channel==MINE",
            startDate=start,
            endDate=end,
            metrics="views",
        ).execute()
        return True, ""
    except Exception as e:
        msg = str(e)
        if "accessNotConfigured" in msg or "has not been used" in msg:
            # Extract the real project name from the error if present, else use known value
            import re as _re

            m = _re.search(r"project[= ](\S+?) ", msg)
            project = m.group(1).rstrip(".") if m else "secure-unison-495301-c8"
            return False, (
                "YouTube Analytics API is disabled on your Google Cloud project.\n\n"
                "  Fix (one-time, 30 seconds):\n"
                f"    1. Open: https://console.developers.google.com/apis/api/"
                f"youtubeanalytics.googleapis.com/overview?project={project}\n"
                "    2. Click  Enable\n"
                "    3. Wait ~1 minute, then re-run option 4 again\n\n"
                "  This is separate from the YouTube Data API — both must be enabled.\n"
                f"  (Your GCP project: {project})"
            )
        if "403" in msg:
            return (
                False,
                f"Analytics permission denied (403) — check OAuth scopes include yt-analytics.readonly.\n  {msg[:400]}",
            )
        return False, f"Analytics probe failed: {msg[:500]}"


def _recency_key(row):
    """Sort newest-first by published_at, then by id."""
    from datetime import datetime, timezone

    when = row.published_at
    if when is None:
        when = datetime.min.replace(tzinfo=timezone.utc)
    elif when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (when, row.id or 0)


def young_days() -> float:
    """`SYNC_YOUNG_DAYS` (default 8): a live video this young is always synced (#918)."""
    import os

    try:
        return max(0.0, float(os.getenv("SYNC_YOUNG_DAYS", "") or 8))
    except ValueError:
        return 8.0


def _to_sync(rows: list, limit: int) -> list:
    """Every live video younger than `young_days()`, then the newest `limit`, newest first.

    Three-newest-only let a video age past its 24h snapshot and its first days of views
    by day at five uploads a week (#918).
    """
    from datetime import datetime, timedelta, timezone

    ordered = sorted(rows, key=_recency_key, reverse=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=young_days())
    young = [r for r in ordered if _recency_key(r)[0] >= cutoff]
    picked = young + [r for r in ordered[: max(1, limit)] if r not in young]
    return sorted(picked, key=_recency_key, reverse=True)


def sync_channel(channel_id: str | None = None, *, limit: int = 3) -> int:
    if not _analytics_enabled():
        print("Set YOUTUBE_ANALYTICS_SYNC=true in .env")
        return 1

    channel_id = resolve_channel_id(channel_id)
    repo = get_publish_log_repository()
    if not hasattr(repo, "list_uploaded_for_channel"):
        print("Publish log list_uploaded not available for this storage backend.")
        return 1

    # Pre-check the API before iterating — catches disabled API early
    ok, err = _probe_analytics_api(channel_id)
    if not ok:
        print(f"\n  {err}\n")
        return 1

    # Every young video (its first days are what the snapshots and the view curve need),
    # then the most recent `limit` - older videos already have metrics and re-pulling all
    # of them every run wastes quota/time.
    rows = _to_sync(
        [r for r in repo.list_uploaded_for_channel(channel_id) if r.youtube_video_id], limit
    )

    synced = 0
    for row in rows:
        title = (row.detail or "").strip() or "(untitled)"
        result = refresh_publish_metrics(
            content_run_id=row.content_run_id,
            youtube_video_id=row.youtube_video_id,
            channel_id=channel_id,
            title=row.detail or "",
            publish_log_id=row.id,
        )
        mark = "✓" if result else "·"
        short = title if len(title) <= 60 else title[:57] + "…"
        print(f"  {mark} {short}  [{row.youtube_video_id}]")
        if result:
            synced += 1

    print(f"\n  Synced {synced}/{len(rows)} recent video(s) for {channel_id}")
    # #940: lifetime views for every live video (the sync's own numbers are a 28-day window).
    from analytics import youtube_metrics
    from storage.repositories.publish_log import is_seeded

    live = [
        r
        for r in repo.list_uploaded_for_channel(channel_id)
        if r.youtube_video_id and not is_seeded(r)
    ]
    counts = youtube_metrics.fetch_lifetime_views(
        [r.youtube_video_id for r in live], channel_id=channel_id
    )
    if counts:
        stored = youtube_metrics.store_lifetime_views(live, counts)
        print(f"  Lifetime views: {stored} video(s)")
    # #934: the whole channel's views by day, for the goal's scoreboard.
    from core.success.goals import sync_channel_views

    days = sync_channel_views(channel_id)
    if days:
        print(f"  Channel views by day: {days} day(s) kept for the scoreboard (ops scoreboard)")
    # #114: viewers' questions on your own uploads - opt-in, about 1 unit per video.
    from analytics import mailbag

    if mailbag.sync_enabled():
        data = mailbag.fetch(channel_id)
        print(f"  Mailbag: {len(data.get('clusters') or [])} question(s) (ops mailbag)")
    if synced > 0:
        print("  Best-bet recommendations will reflect real engagement on next run.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Sync YouTube Analytics metrics")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Newest videos to sync besides every one younger than SYNC_YOUNG_DAYS (default 3)",
    )
    args = parser.parse_args()
    raise SystemExit(sync_channel(args.channel, limit=args.limit))


if __name__ == "__main__":
    main()
