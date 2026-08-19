"""
Seed publish_log + performance_entries from TapIn Media export summary.

Usage:
    py -m analytics.seed_tapin
    py -m analytics.seed_tapin --csv path/to/export.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from analytics.post_timing import PostSlot, _load_static_post_schedule, slots_for_topic
from storage.db import check_database_connection, is_database_configured
from storage.init_db import main as init_db_main
from storage.repositories.performance_memory import get_performance_memory_repository
from storage.repositories.publish_log import get_publish_log_repository

_SEED_FILE = os.path.join(os.path.dirname(__file__), "tapin_performance_seed.json")
CHANNEL_ID = "tapin"


def _load_seed(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _alignment_from_video(video: dict[str, Any]) -> float:
    """Primary learning signal: engaged-view rate (0–100 scale)."""
    rate = float(video.get("engaged_rate", 0))
    return round(rate * 100, 2)


def _performance_entry(video: dict[str, Any], channel_id: str) -> dict[str, Any]:
    views = int(video.get("views", 0))
    engaged = float(video.get("engaged_rate", 0))
    return {
        "domain": video.get("domain", "neutral"),
        "alignment_score": _alignment_from_video(video),
        "engaged_rate": engaged,
        "views": views,
        "likes": int(video.get("likes", 0)),
        "subscribers_gained": int(video.get("subscribers_gained", 0)),
        "title": video.get("title", ""),
        "source": "tapin_seed",
        "channel_id": channel_id,
    }


def _historical_publish_at(domain: str, index: int, channel_id: str) -> datetime:
    """Stagger seed publishes across channel slot windows for post-timing learning."""
    topic = "UFC 300 highlights" if domain == "ufc" else "GTA 6 gaming news"
    slots = slots_for_topic(channel_id, topic)
    if not slots:
        schedule = _load_static_post_schedule(channel_id)
        slots = schedule.slots or (PostSlot(4, 18, 0),)
    slot = slots[index % len(slots)]
    weeks_back = (index // len(slots)) + 1
    try:
        tz = ZoneInfo(_load_static_post_schedule(channel_id).timezone)
    except Exception:
        tz = ZoneInfo("America/New_York")
    local_now = datetime.now(tz)
    target_date = local_now.date() - timedelta(weeks=weeks_back)
    while target_date.weekday() != slot.weekday:
        target_date -= timedelta(days=1)
    local_dt = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        slot.hour,
        slot.minute,
        tzinfo=tz,
    )
    return local_dt.astimezone(timezone.utc)


def _import_videos(videos: list[dict], channel_id: str) -> int:
    perf = get_performance_memory_repository()
    publish = get_publish_log_repository()
    count = 0

    for i, video in enumerate(videos, start=1):
        entry = _performance_entry(video, channel_id)
        perf.log_performance(entry, channel_id)
        domain = str(entry.get("domain", "neutral"))

        metrics = {
            "views": entry["views"],
            "engaged_rate": entry["engaged_rate"],
            "likes": entry["likes"],
            "subscribers_gained": entry["subscribers_gained"],
            "title": entry["title"],
            "domain": domain,
            "source": "tapin_seed",
        }
        publish.create(
            {
                # No originating run — these are historical YouTube videos, not
                # pipeline output. NULL (not the legacy 0 sentinel) so the
                # content_run_id foreign key accepts them.
                "content_run_id": None,
                "channel_id": channel_id,
                "youtube_video_id": f"seed_{channel_id}_{i}",
                "privacy_status": "public",
                "status": "imported",
                "metrics_json": json.dumps(metrics),
                "detail": entry["title"] or "TapIn historical export seed",
                "published_at": _historical_publish_at(domain, i - 1, channel_id),
            }
        )
        count += 1

    return count


def _import_csv(path: str, channel_id: str) -> int:
    videos = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = (row.get("domain") or row.get("niche") or "neutral").strip().lower()
            videos.append(
                {
                    "title": row.get("title") or row.get("video_title") or "",
                    "domain": domain,
                    "views": int(float(row.get("views") or row.get("view_count") or 0)),
                    "engaged_rate": float(
                        row.get("engaged_rate")
                        or row.get("engaged_view_rate")
                        or row.get("engagement_rate")
                        or 0
                    ),
                    "likes": int(float(row.get("likes") or 0)),
                    "subscribers_gained": int(
                        float(row.get("subscribers_gained") or row.get("subs") or 0)
                    ),
                }
            )
    return _import_videos(videos, channel_id)


def seed_tapin(*, seed_path: str = _SEED_FILE, channel_id: str = CHANNEL_ID) -> int:
    if not os.path.isfile(seed_path):
        raise FileNotFoundError(f"Seed file not found: {seed_path}")

    data = _load_seed(seed_path)
    channel_id = data.get("channel_id", channel_id)
    videos = data.get("videos") or []
    return _import_videos(videos, channel_id)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Seed TapIn analytics into Content OS")
    parser.add_argument("--seed", default=_SEED_FILE, help="JSON seed file path")
    parser.add_argument("--csv", help="Optional CSV export (overrides JSON videos)")
    parser.add_argument("--channel", default=CHANNEL_ID)
    parser.add_argument("--init-db", action="store_true", help="Run storage.init_db first")
    args = parser.parse_args(argv)

    if args.init_db:
        if init_db_main() != 0 and is_database_configured():
            return 1

    if is_database_configured():
        ok, detail = check_database_connection()
        if not ok:
            print(f"Database not reachable: {detail}")
            return 1
        print("Using PostgreSQL (authoritative)")
    else:
        print("Using JSON fallbacks (no DATABASE_URL)")

    if args.csv:
        count = _import_csv(args.csv, args.channel)
    else:
        count = seed_tapin(seed_path=args.seed, channel_id=args.channel)

    print(f"Seeded {count} videos for channel '{args.channel}'")
    print("Set CONTENT_CHANNEL_ID=tapin or select TapIn in the CLI to use learned weights.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
