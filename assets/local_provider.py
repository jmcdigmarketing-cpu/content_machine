import os
import random

from core.llm_client import get_model, get_openai_client

from typing import Optional

from assets.base import AssetProvider
from assets.category import detect_category
from assets.types import AssetResult

BASE_VIDEO_DIR = os.path.join("video", "backgrounds")
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = get_openai_client()
    return _client


def _get_subfolders(base_path):
    folders = []
    for root, _, files in os.walk(base_path):
        if any(f.lower().endswith((".mp4", ".mov")) for f in files):
            folders.append(root)
    return folders


def _ai_choose_folder(topic, folders):
    if not folders:
        return None

    folder_list_text = "\n".join(
        f"- {os.path.relpath(f, BASE_VIDEO_DIR)}" for f in folders
    )

    prompt = f"""
Select the most relevant folder for this topic.

Topic:
{topic}

Available folders:
{folder_list_text}

Return ONLY the exact folder path.
No explanation.
"""

    try:
        response = _get_client().chat.completions.create(
            model=get_model(),
            temperature=0,
            messages=[
                {"role": "system", "content": "Select best folder from list."},
                {"role": "user", "content": prompt},
            ],
        )
        choice = response.choices[0].message.content.strip()
        for folder in folders:
            if os.path.relpath(folder, BASE_VIDEO_DIR) == choice:
                return folder
    except Exception:
        pass
    return None


class LocalAssetProvider(AssetProvider):
    name = "local"

    def find_video(self, topic: str, category: str, channel_id=None) -> Optional[AssetResult]:
        if not os.path.exists(BASE_VIDEO_DIR):
            return None

        category_path = os.path.join(BASE_VIDEO_DIR, category)
        if not os.path.exists(category_path):
            category_path = BASE_VIDEO_DIR

        candidate_folders = _get_subfolders(category_path) or _get_subfolders(BASE_VIDEO_DIR)
        if not candidate_folders:
            return None

        from assets.background_query import resolve_background_query

        pick_topic = resolve_background_query(topic, category, channel_id)
        chosen_folder = _ai_choose_folder(pick_topic, candidate_folders) or random.choice(
            candidate_folders
        )

        video_files = [
            os.path.join(chosen_folder, f)
            for f in os.listdir(chosen_folder)
            if f.lower().endswith((".mp4", ".mov"))
        ]
        if not video_files:
            return None

        path = random.choice(video_files)
        return AssetResult(path=path, provider=self.name, query=topic)
