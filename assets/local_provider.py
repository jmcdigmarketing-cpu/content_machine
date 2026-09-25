import json
import os
import random

from typing import Optional

from assets.base import AssetProvider
from assets.category import detect_category
from assets.types import AssetResult
from core.logging import get_logger

logger = get_logger("assets.local")

BASE_VIDEO_DIR = os.path.join("video", "backgrounds")


def _nearest_license_file(clip_path: str) -> str | None:
    base = os.path.abspath(BASE_VIDEO_DIR)
    current = os.path.abspath(os.path.dirname(clip_path))
    while current == base or current.startswith(base + os.sep):
        candidate = os.path.join(current, "license.yaml")
        if os.path.isfile(candidate):
            return candidate
        if current == base:
            break
        current = os.path.dirname(current)
    return None


def _license_attribution(clip_path: str) -> str | None:
    sidecar = _nearest_license_file(clip_path)
    if not sidecar:
        return None
    try:
        with open(sidecar, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("expected an object")
        owner = str(data.get("owner") or "").strip()
        license_name = str(data.get("license") or "").strip()
        commercial = data.get("commercial_use")
        parts = []
        if license_name:
            parts.append(license_name)
        if owner:
            parts.append(f"owner: {owner}")
        if commercial is not None:
            parts.append(f"commercial use: {'yes' if bool(commercial) else 'no'}")
        return "; ".join(parts) or None
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("Local clip license unreadable (%s): %s", sidecar, exc)
        return None


def _get_subfolders(base_path):
    folders = []
    for root, _, files in os.walk(base_path):
        if any(f.lower().endswith((".mp4", ".mov")) for f in files):
            folders.append(root)
    return folders


_GENERIC_FOLDER_NAMES = frozenset({"gaming", "sports", "general", "video", "backgrounds"})


def _keyword_choose_folder(topic: str, folders: list[str]) -> str | None:
    """Pick a library folder whose name appears in the original topic.

    Stock-query rewrite turns "Fortnite reload" into "video game gameplay
    esports", so this must run on the operator topic — not the rewrite.
    """
    hay = (topic or "").lower()
    if not hay or not folders:
        return None
    scored: list[tuple[int, str]] = []
    for folder in folders:
        name = os.path.basename(folder).lower().replace("_", " ").replace("-", " ").strip()
        if not name or name in _GENERIC_FOLDER_NAMES:
            continue
        if name in hay:
            scored.append((len(name), folder))
            continue
        tokens = [tok for tok in name.split() if len(tok) >= 3 and tok not in _GENERIC_FOLDER_NAMES]
        hits = [tok for tok in tokens if tok in hay]
        if hits:
            scored.append((max(len(tok) for tok in hits), folder))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _alias_choose_folder(topic: str, folders: list[str], channel_id=None) -> str | None:
    """The footage folder of the first franchise playlist the topic matches (#786).

    "NFL draft" names no folder, but the NFL playlist row in config/playlists.json lists
    `footage: ["Madden 26"]`, so an NFL Short cuts Madden gameplay instead of a random game.
    """
    try:
        from core.playlists import playlist_map, _matches

        rows = playlist_map(channel_id or "tapin")
    except Exception as exc:
        logger.debug("footage alias skipped: %s", exc)
        return None
    hay = (topic or "").lower()
    by_name = {os.path.basename(f).casefold(): f for f in folders}
    for row in rows:
        if not _matches(hay, [str(k) for k in row.get("keys") or []]):
            continue
        for name in row.get("footage") or []:
            folder = by_name.get(str(name).casefold())
            if folder:
                return folder
    return None


def _ai_choose_folder(topic, folders):
    if not folders:
        return None

    folder_list_text = "\n".join(f"- {os.path.relpath(f, BASE_VIDEO_DIR)}" for f in folders)

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

    def candidate_clips(self, topic: str, category: str, channel_id=None) -> list[str]:
        """Every clip in the folder this topic picks (one game), for multi-shot backgrounds
        (#782). `find_video` draws its single clip from the same list."""
        if not os.path.exists(BASE_VIDEO_DIR):
            return []

        category_path = os.path.join(BASE_VIDEO_DIR, category)
        if not os.path.exists(category_path):
            category_path = BASE_VIDEO_DIR

        candidate_folders = _get_subfolders(category_path) or _get_subfolders(BASE_VIDEO_DIR)
        if not candidate_folders:
            return []

        from assets.background_query import resolve_background_query

        chosen_folder = _keyword_choose_folder(topic, candidate_folders) or _alias_choose_folder(
            topic, candidate_folders, channel_id
        )
        if not chosen_folder:
            pick_topic = resolve_background_query(topic, category, channel_id)
            chosen_folder = _ai_choose_folder(pick_topic, candidate_folders) or random.choice(
                candidate_folders
            )
        return [
            os.path.join(chosen_folder, f)
            for f in sorted(os.listdir(chosen_folder))
            if f.lower().endswith((".mp4", ".mov"))
        ]

    def find_video(self, topic: str, category: str, channel_id=None) -> Optional[AssetResult]:
        video_files = self.candidate_clips(topic, category, channel_id)
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
        return AssetResult(
            path=path,
            provider=self.name,
            query=topic,
            attribution=_license_attribution(path),
        )
