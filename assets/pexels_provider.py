import os

import requests

from assets.base import AssetProvider
from assets.catalog import find_cached, register
from assets.download import CACHE_DIR, download_file, safe_filename
from assets.types import AssetResult
from config.settings import get_settings


class PexelsAssetProvider(AssetProvider):
    name = "pexels"

    def is_configured(self) -> bool:
        return bool(get_settings().pexels_api_key)

    def find_video(self, topic: str, category: str, channel_id=None) -> AssetResult | None:
        key = get_settings().pexels_api_key
        if not key:
            return None

        from assets.background_query import is_abstract_stock_text
        from assets.category import search_query

        query = search_query(topic, category, channel_id)
        cached = find_cached(query, self.name)
        if cached:
            return AssetResult(path=cached, provider=self.name, query=query, source_id="cached")

        try:
            response = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": key},
                params={
                    "query": query,
                    "per_page": 5,
                    "orientation": "portrait",
                },
                timeout=15,
            )
            if response.status_code != 200:
                return None

            videos = response.json().get("videos") or []
            for video in videos:
                tags = " ".join(video.get("tags") or [])
                alt = str(video.get("url") or "")
                if is_abstract_stock_text(tags) or is_abstract_stock_text(alt):
                    continue
                files = video.get("video_files") or []
                vertical = [
                    f
                    for f in files
                    if f.get("height", 0) >= f.get("width", 0) and f.get("link")
                ]
                pick = vertical[0] if vertical else (files[0] if files else None)
                if not pick:
                    continue

                vid = str(video.get("id", "unknown"))
                dest = os.path.join(
                    CACHE_DIR,
                    f"pexels_{safe_filename(vid)}.mp4",
                )
                download_file(pick["link"], dest)
                user = video.get("user", {}).get("name", "Pexels")
                register(dest, self.name, vid, query, f"Video by {user} on Pexels")
                return AssetResult(
                    path=dest,
                    provider=self.name,
                    source_id=vid,
                    query=query,
                    attribution=f"Video by {user} on Pexels",
                )
        except Exception:
            return None

        return None
