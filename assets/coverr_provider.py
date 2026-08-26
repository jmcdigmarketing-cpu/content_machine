"""Coverr stock-video provider (Wave A).

Search URL confirmed from Coverr's public docs (https://api.coverr.co/docs/videos/):
GET https://api.coverr.co/videos?query=…&urls=true with Authorization: Bearer {key}.
No key ⇒ is_configured() is false and the manager chain continues to Pexels.
Prefer clips without recognisable faces (Coverr model-release caveat).
"""

from __future__ import annotations

import os
import re

import requests

from assets.base import AssetProvider
from assets.catalog import find_cached, register
from assets.download import CACHE_DIR, download_file, safe_filename
from assets.types import AssetResult
from config.settings import get_settings

# Tags/title/description tokens that usually mean a recognisable person is in frame.
# Avoid generic "people"/"person" — stock copy often says "no people".
_FACE_MARKERS = (
    "face",
    "faces",
    "man",
    "woman",
    "girl",
    "boy",
    "couple",
    "portrait",
    "smiling",
    "smile",
    "crowd",
)


def _coverr_key() -> str:
    return (os.getenv("COVERR_API_KEY") or get_settings().coverr_api_key or "").strip()


def _looks_like_face(hit: dict) -> bool:
    blob = " ".join(
        [
            str(hit.get("title") or ""),
            str(hit.get("description") or ""),
            " ".join(hit.get("tags") or []),
        ]
    ).lower()
    return any(re.search(rf"\b{re.escape(marker)}\b", blob) for marker in _FACE_MARKERS)


class CoverrAssetProvider(AssetProvider):
    name = "coverr"

    def is_configured(self) -> bool:
        return bool(_coverr_key())

    def find_video(self, topic: str, category: str, channel_id=None) -> AssetResult | None:
        key = _coverr_key()
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
                "https://api.coverr.co/videos",
                headers={"Authorization": f"Bearer {key}"},
                params={
                    "query": query,
                    "page_size": 8,
                    "urls": "true",
                },
                timeout=15,
            )
            if response.status_code != 200:
                return None

            hits = list(response.json().get("hits") or [])
            hits.sort(key=lambda h: (not bool(h.get("is_vertical")),))
            for hit in hits:
                if _looks_like_face(hit):
                    continue
                tags = " ".join(hit.get("tags") or [])
                meta = f"{hit.get('title') or ''} {hit.get('description') or ''} {tags}"
                if is_abstract_stock_text(meta):
                    continue
                urls = hit.get("urls") or {}
                link = urls.get("mp4_download") or urls.get("mp4")
                if not link:
                    continue
                vid = str(hit.get("id", "unknown"))
                dest = os.path.join(CACHE_DIR, f"coverr_{safe_filename(vid)}.mp4")
                download_file(link, dest)
                title = str(hit.get("title") or "Coverr")
                register(dest, self.name, vid, query, f"Video from Coverr: {title}")
                return AssetResult(
                    path=dest,
                    provider=self.name,
                    source_id=vid,
                    query=query,
                    attribution=f"Video from Coverr: {title}",
                )
        except Exception:
            return None

        return None
