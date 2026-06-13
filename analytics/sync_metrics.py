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


def sync_channel(channel_id: str | None = None) -> int:
    if not _analytics_enabled():
        print("Set YOUTUBE_ANALYTICS_SYNC=true in .env")
        return 1

    channel_id = resolve_channel_id(channel_id)
    repo = get_publish_log_repository()
    if not hasattr(repo, "list_uploaded_for_channel"):
        print("Publish log list_uploaded not available for this storage backend.")
        return 1

    # Pre-check the API before iterating all videos — catches disabled API early
    ok, err = _probe_analytics_api(channel_id)
    if not ok:
        print(f"\n  {err}\n")
        return 1

    rows = repo.list_uploaded_for_channel(channel_id)
    synced = 0
    for row in rows:
        if not row.youtube_video_id:
            continue
        result = refresh_publish_metrics(
            content_run_id=row.content_run_id,
            youtube_video_id=row.youtube_video_id,
            channel_id=channel_id,
            title=row.detail or "",
            publish_log_id=row.id,
        )
        if result:
            synced += 1
            print(f"  ✓ Synced video {row.youtube_video_id}")

    total = sum(1 for r in rows if r.youtube_video_id)
    print(f"\n  Synced {synced}/{total} uploaded video(s) for {channel_id}")
    if synced > 0:
        print("  Best-bet recommendations will reflect real engagement on next run.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Sync YouTube Analytics metrics")
    parser.add_argument("--channel", default="tapin")
    args = parser.parse_args()
    raise SystemExit(sync_channel(args.channel))


if __name__ == "__main__":
    main()
