"""Per-channel YouTube competitor channel tracking (Phase I)."""

from __future__ import annotations

import json
import os
from functools import lru_cache

from config.paths import DATA_DIR, ROOT_DIR

COMPETITORS_DIR = os.path.join(ROOT_DIR, "config", "competitors")


def competitors_config_path(channel_id: str) -> str:
    return os.path.join(COMPETITORS_DIR, f"{channel_id}.json")


def competitors_data_path(channel_id: str) -> str:
    return os.path.join(DATA_DIR, f"competitors_{channel_id}.json")


@lru_cache(maxsize=16)
def get_competitor_channels(channel_id: str) -> list[dict[str, str]]:
    path = competitors_config_path(channel_id)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    channels = data.get("youtube_channels") or data.get("channels") or []
    out = []
    for item in channels:
        if isinstance(item, dict) and item.get("id"):
            row = {
                "id": str(item["id"]),
                "label": str(item.get("label", item["id"])),
            }
            note = str(item.get("note") or item.get("status") or "").strip()
            if note:
                row["note"] = note
            out.append(row)
        elif isinstance(item, str):
            out.append({"id": item, "label": item})
    return out
