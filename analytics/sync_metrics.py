"""
Sync YouTube Analytics for uploaded videos in publish_log.

Usage:
    py -m analytics.sync_metrics --channel tapin
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

from analytics.youtube_metrics import _analytics_enabled, refresh_publish_metrics
from config.channels import resolve_channel_id
from config.paths import DATA_DIR
from core.logging import get_logger
from storage.repositories.publish_log import get_publish_log_repository, video_title

logger = get_logger("analytics.sync_metrics")

# Wave 113: the sync ran only when the operator ran `ops morning` or `ops all`. Overnight and the
# upload worker (every 15 minutes) sync once a day without them; this stamps the last sync.
SYNC_STAMP_FILE = os.path.join(DATA_DIR, "metrics_synced.json")
SYNC_EVERY_HOURS = 20.0
RETRY_HOURS = 2.0


def _stamps() -> dict:
    try:
        with open(SYNC_STAMP_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def mark_synced(channel_id: str, *, now: datetime | None = None) -> None:
    data = _stamps()
    data[channel_id] = (now or datetime.now(timezone.utc)).isoformat()
    try:
        os.makedirs(os.path.dirname(SYNC_STAMP_FILE) or ".", exist_ok=True)
        tmp = f"{SYNC_STAMP_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(tmp, SYNC_STAMP_FILE)
    except OSError as exc:
        logger.debug("sync stamp not written: %s", exc)


def last_synced(channel_id: str) -> datetime | None:
    raw = _stamps().get(channel_id)
    try:
        when = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def maybe_sync(channel_id: str, *, now: datetime | None = None) -> bool:
    """Sync when the last one is over SYNC_EVERY_HOURS old (or never ran). True when it ran.
    Fail-open: an unattended caller never stops on it."""
    moment = now or datetime.now(timezone.utc)
    last = last_synced(channel_id)
    if last is not None and (moment - last).total_seconds() < SYNC_EVERY_HOURS * 3600:
        return False
    tried = last_synced(f"{channel_id}:tried")
    if tried is not None and (moment - tried).total_seconds() < RETRY_HOURS * 3600:
        return False  # a failed sync (analytics off, API down) is not retried every 15 minutes
    code = 1
    try:
        code = sync_channel(channel_id)
    except Exception as exc:
        logger.warning("unattended metrics sync failed: %s: %s", type(exc).__name__, exc)
    if code != 0:
        mark_synced(f"{channel_id}:tried", now=moment)
    return True


def sync_note(channel_id: str, *, now: datetime | None = None) -> str:
    """For health's unmeasured line: when the sync last ran, and that YouTube lags."""
    last = last_synced(channel_id)
    if last is None:
        return "no unattended sync recorded yet; YouTube's numbers lag 2-3 days"
    hours = max(0, int(((now or datetime.now(timezone.utc)) - last).total_seconds() // 3600))
    return f"last sync {hours} h ago; YouTube's numbers lag 2-3 days"


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

    from analytics import first_day

    started = first_day._now()
    synced = 0
    for row in rows:
        title = video_title(row)
        result = refresh_publish_metrics(
            content_run_id=row.content_run_id,
            youtube_video_id=row.youtube_video_id,
            channel_id=channel_id,
            title=video_title(row, fallback=""),
            publish_log_id=row.id,
        )
        mark = "✓" if result else "·"
        short = title if len(title) <= 60 else title[:57] + "…"
        print(f"  {mark} {short}  [{row.youtube_video_id}]")
        if result:
            synced += 1

    print(f"\n  Synced {synced}/{len(rows)} recent video(s) for {channel_id}")
    for line in first_day.recent_lines(channel_id, since=started):  # #49
        print(f"  {line}")
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
    # #1128: each video's privacy as YouTube has it now - a scheduled upload turns public at
    # its slot and a held one is made public in Studio, and the record never asked again.
    from analytics import privacy_sync

    for line in privacy_sync.sync_lines(privacy_sync.sync_privacy(channel_id)):
        print(f"  {line}")
    # #934: the whole channel's views by day, for the goal's scoreboard.
    from core.success.goals import sync_channel_views

    days = sync_channel_views(channel_id)
    if days:
        print(f"  Channel views by day: {days} day(s) kept for the scoreboard (ops scoreboard)")
    # #954: YouTube's own YPP numbers - Shorts views 90 days, long-form hours 12 months,
    # subscribers - with ads excluded, as YouTube excludes them.
    from core.ypp_readiness import save_ypp_numbers

    numbers = youtube_metrics.fetch_ypp_numbers(channel_id=channel_id)
    try:  # #1832 (wave 135): a Short past 1,000 organic views in a day - one toast
        from core.success.scorecard import toast_breakouts

        for title in toast_breakouts(channel_id):
            print(f"  Breakout: {title}")
    except Exception as exc:
        print(f"  Breakout check skipped: {exc}")
    if numbers:
        save_ypp_numbers(channel_id, numbers)
        subs = numbers.get("subscribers")
        print(
            f"  YPP numbers (ads excluded): {subs if subs is not None else '?'} subscribers, "
            f"{float(numbers.get('long_hours_365d') or 0):,.0f} long-form hours, "
            f"{int(numbers.get('shorts_views_90d') or 0):,} Shorts views (ops ypp)"
        )
    # #951: thumbnail impressions and click-through from the Reporting API's reach report.
    from analytics import reach_report

    line = reach_report.sync_reach(channel_id)
    if line:
        print(line)
    # #114: viewers' questions on your own uploads - opt-in, about 1 unit per video.
    from analytics import mailbag

    if mailbag.sync_enabled():
        data = mailbag.fetch(channel_id)
        print(f"  Mailbag: {len(data.get('clusters') or [])} question(s) (ops mailbag)")
    if synced > 0:
        print("  Best-bet recommendations will reflect real engagement on next run.")
    mark_synced(channel_id)
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
    from core.console_encoding import ensure_utf8_stdout

    ensure_utf8_stdout()  # #1135: run directly under a redirect, the check mark killed it
    raise SystemExit(sync_channel(args.channel, limit=args.limit))


if __name__ == "__main__":
    main()
