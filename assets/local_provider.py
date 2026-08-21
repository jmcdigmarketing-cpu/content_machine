import os
import random

from typing import Optional

from assets.base import AssetProvider
from assets.category import detect_category
from assets.types import AssetResult
from core.logging import get_logger

logger = get_logger("assets.local")

BASE_VIDEO_DIR = os.path.join("video", "backgrounds")


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
        from core.llm_router import complete

        # Picking a background folder from a list is trivial → cheap tier.
        choice = complete(
            prompt,
            tier="cheap",
            system="Select best folder from list.",
            temperature=0,
            max_tokens=120,
        ).strip()
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
        try:
            from assets.clip_memory import pick_unseen

            chosen = pick_unseen(video_files)
            if chosen:
                path = chosen
        except Exception as exc:
            logger.debug("clip anti-repeat skipped: %s", exc)
        return AssetResult(path=path, provider=self.name, query=topic)
