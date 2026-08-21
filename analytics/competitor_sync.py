"""
Competitor upload tracking — free YouTube RSS first, Data API fallback.

    py -m analytics.competitor_sync --channel tapin
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any

from config.competitors import competitors_data_path, get_competitor_channels
from config.paths import ensure_data_dir
from core.logging import get_logger

logger = get_logger("analytics.competitor_sync")

# API fallback is 3 units per competitor (channels.list + playlistItems.list).
_API_UNITS = 3
_sync_api_units = 0


def _max_api_units() -> int | None:
    raw = os.getenv("COMPETITOR_SYNC_MAX_UNITS", "30").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return None
    try:
        val = int(float(raw))
    except ValueError:
        return None
    return val if val > 0 else None


def _reserve_units() -> int:
    raw = os.getenv("COMPETITOR_SYNC_RESERVE_UNITS", "1600").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return 0
    try:
        val = int(float(raw))
    except ValueError:
        return 1600
    return max(0, val)


def youtube_api_fallback_block_reason(
    *,
    remaining: int | None = None,
    units_needed: int = _API_UNITS,
    used_this_sync: int | None = None,
) -> str | None:
    """Why Data API fallback must not run, or None when the call is allowed."""
    used = _sync_api_units if used_this_sync is None else used_this_sync
    cap = _max_api_units()
    if cap is not None and used + units_needed > cap:
        return (
            f"competitor-sync unit cap: {used}+{units_needed} would exceed {cap} "
            "(RSS-only for the rest of this sync)"
        )
    reserve = _reserve_units()
    if remaining is None:
        try:
            from apis.youtube_quota import get_usage_summary

            remaining = int(get_usage_summary().get("remaining") or 0)
        except Exception as exc:
            logger.debug("competitor-sync quota read skipped: %s", exc)
            remaining = None
    if remaining is not None and reserve and remaining < reserve + units_needed:
        return f"competitor-sync: {remaining} YouTube units left, " f"reserve {reserve} for uploads"
    return None


def _rss_enabled() -> bool:
    return os.getenv("COMPETITOR_SYNC_RSS", "true").lower() not in ("0", "false", "no")


def _get_youtube_service(channel_id: str):
    """
    Competitor uploads are public data — prefer the Data API key (no OAuth scope
    needed). Fall back to channel OAuth only if no key is configured.
    """
    from youtube.oauth import live_youtube_forbidden

    if live_youtube_forbidden():
        logger.debug("live YouTube client forbidden (C9)")
        return None
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if api_key:
        try:
            from googleapiclient.discovery import build

            return build(
                "youtube",
                "v3",
                developerKey=api_key,
                cache_discovery=False,
                static_discovery=True,
            )
        except Exception as exc:
            logger.debug("API-key YouTube service build failed: %s", exc)

    from youtube.oauth import get_youtube_service

    return get_youtube_service(channel_id)


def fetch_channel_recent_videos_api(
    service,
    youtube_channel_id: str,
    *,
    max_results: int = 8,
) -> list[dict[str, Any]]:
    """Recent uploads via Data API (costs quota)."""
    try:
        ch = service.channels().list(part="contentDetails", id=youtube_channel_id).execute()
        items = ch.get("items") or []
        if not items:
            return []
        uploads_id = (
            (items[0].get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")
        )
        if not uploads_id:
            return []

        pl = (
            service.playlistItems()
            .list(
                playlistId=uploads_id,
                part="snippet,contentDetails",
                maxResults=max_results,
            )
            .execute()
        )
        videos = []
        for item in pl.get("items") or []:
            sn = item.get("snippet") or {}
            videos.append(
                {
                    "video_id": (item.get("contentDetails") or {}).get("videoId", ""),
                    "title": sn.get("title", ""),
                    "published_at": sn.get("publishedAt", ""),
                    "source": "youtube_api",
                }
            )
        return videos
    except Exception as exc:
        logger.warning("Competitor API fetch failed for %s: %s", youtube_channel_id, exc)
        return []


def fetch_channel_recent_videos(
    channel_id: str,
    youtube_channel_id: str,
    *,
    service=None,
    max_results: int = 8,
) -> list[dict[str, Any]]:
    """RSS first (free), API fallback."""
    global _sync_api_units
    if _rss_enabled():
        from analytics.youtube_rss import fetch_channel_uploads_rss

        videos = fetch_channel_uploads_rss(youtube_channel_id, max_results=max_results)
        if videos:
            return videos

    blocked = youtube_api_fallback_block_reason()
    if blocked:
        logger.warning("%s", blocked)
        return []

    if service is None:
        service = _get_youtube_service(channel_id)
    if not service:
        return []

    from apis.youtube_quota import record_usage

    record_usage(units=_API_UNITS)
    _sync_api_units += _API_UNITS
    return fetch_channel_recent_videos_api(service, youtube_channel_id, max_results=max_results)


def sync_competitors(channel_id: str) -> dict[str, Any]:
    global _sync_api_units
    _sync_api_units = 0
    channels = get_competitor_channels(channel_id)
    if not channels:
        return {"channel_id": channel_id, "competitors": [], "error": "no config"}

    service = None
    if not _rss_enabled():
        service = _get_youtube_service(channel_id)
        if not service:
            return {
                "channel_id": channel_id,
                "competitors": [],
                "error": "youtube not configured",
            }

    snapshot = {
        "channel_id": channel_id,
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "sync_method": "youtube_rss" if _rss_enabled() else "youtube_api",
        "competitors": [],
    }

    for comp in channels:
        videos = fetch_channel_recent_videos(
            channel_id,
            comp["id"],
            service=service,
        )
        snapshot["competitors"].append(
            {
                "youtube_channel_id": comp["id"],
                "label": comp["label"],
                "recent_videos": videos,
            }
        )

    ensure_data_dir()
    path = competitors_data_path(channel_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync competitor channel uploads")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--force", action="store_true", help="Sync even if cache is fresh")
    args = parser.parse_args()

    if not args.force:
        from analytics.competitor_context import is_snapshot_stale

        if not is_snapshot_stale(args.channel):
            print(f"Competitor snapshot fresh for {args.channel} (use --force)")
            return 0

    snap = sync_competitors(args.channel)
    n = len(snap.get("competitors") or [])
    method = snap.get("sync_method", "?")
    print(f"Synced {n} competitors via {method} for {args.channel}")
    if snap.get("error"):
        print(f"  Note: {snap['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
