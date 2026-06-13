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


def _rss_enabled() -> bool:
    return os.getenv("COMPETITOR_SYNC_RSS", "true").lower() not in ("0", "false", "no")


def _get_youtube_service(channel_id: str):
    """
    Competitor uploads are public data — prefer the Data API key (no OAuth scope
    needed). Fall back to channel OAuth only if no key is configured.
    """
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if api_key:
        try:
            from googleapiclient.discovery import build

            return build("youtube", "v3", developerKey=api_key, cache_discovery=False)
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
    if _rss_enabled():
        from analytics.youtube_rss import fetch_channel_uploads_rss

        videos = fetch_channel_uploads_rss(youtube_channel_id, max_results=max_results)
        if videos:
            return videos

    if service is None:
        service = _get_youtube_service(channel_id)
    if not service:
        return []

    from apis.youtube_quota import record_usage

    record_usage(units=3)
    return fetch_channel_recent_videos_api(service, youtube_channel_id, max_results=max_results)


def sync_competitors(channel_id: str) -> dict[str, Any]:
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
