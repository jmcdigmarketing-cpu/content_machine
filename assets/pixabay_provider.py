import os

import requests

from assets.base import AssetProvider
from assets.catalog import find_cached, register
from assets.download import CACHE_DIR, download_file, safe_filename
from assets.types import AssetResult
from config.settings import get_settings


class PixabayAssetProvider(AssetProvider):
    name = "pixabay"

    def is_configured(self) -> bool:
        return bool(get_settings().pixabay_api_key)

    def find_video(self, topic: str, category: str, channel_id=None) -> AssetResult | None:
        key = get_settings().pixabay_api_key
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
                "https://pixabay.com/api/videos/",
                params={
                    "key": key,
                    "q": query,
                    "per_page": 5,
                },
                timeout=15,
            )
            if response.status_code != 200:
                return None

            hits = response.json().get("hits") or []
            for hit in hits:
                meta = " ".join(hit.get("tags", "").split(","))
                if is_abstract_stock_text(meta):
                    continue
                videos = hit.get("videos") or {}
                pick = (
                    videos.get("medium")
                    or videos.get("small")
                    or videos.get("tiny")
                )
                if not pick or not pick.get("url"):
                    continue

                vid = str(hit.get("id", "unknown"))
                dest = os.path.join(CACHE_DIR, f"pixabay_{safe_filename(vid)}.mp4")
                download_file(pick["url"], dest)
                user = hit.get("user", "Pixabay")
                register(dest, self.name, vid, query, f"Video by {user} on Pixabay")
                return AssetResult(
                    path=dest,
                    provider=self.name,
                    source_id=vid,
                    query=query,
                    attribution=f"Video by {user} on Pixabay",
                )
        except Exception:
            return None

        return None
