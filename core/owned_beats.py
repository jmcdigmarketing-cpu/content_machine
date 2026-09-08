"""#416: cut owned gameplay between scene-plan beats. Never stock (§26)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from core.logging import get_logger
from video.scene_plan import Scene, plan_scenes

logger = get_logger("core.owned_beats")


def _topic_tokens(topic: str) -> list[str]:
    return [t for t in re.sub(r"[^a-z0-9]+", " ", (topic or "").lower()).split() if len(t) > 2]


def assign_owned_clips(
    scenes: list[Scene],
    index: dict[str, Any],
    *,
    topic: str,
) -> list[str]:
    """Map beats to clip_index paths. Empty index -> [] (keep the single loop)."""
    clips = (index or {}).get("clips") or {}
    if not scenes or not isinstance(clips, dict) or not clips:
        return []
    tokens = _topic_tokens(topic)
    ranked: list[tuple[int, float, str]] = []
    for path, meta in clips.items():
        if not path:
            continue
        blob = f"{path} {((meta or {}).get('source') or '')}".lower()
        score = sum(1 for tok in tokens if tok in blob)
        duration = float((meta or {}).get("duration_s") or 0.0)
        ranked.append((score, duration, str(path)))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    paths = []
    for _score, _dur, path in ranked:
        meta = clips.get(path) or {}
        hud = meta.get("hud")
        if hud is None and os.path.isfile(path):
            try:
                from core.hud_detect import detect_hud

                hud = detect_hud(path)
            except Exception as exc:
                logger.debug("hud probe skipped for %s: %s", path, exc)
        if hud is True:
            continue
        paths.append(str(path))
    if not paths:
        return []
    if len(scenes) > 1 and len(paths) < 2:
        return []
    return [paths[i % len(paths)] for i in range(len(scenes))]


def load_clip_index(path: str | None = None) -> dict[str, Any]:
    from config.paths import CLIP_INDEX_FILE

    target = path or CLIP_INDEX_FILE
    if not os.path.isfile(target):
        return {"clips": {}}
    try:
        with open(target, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("clips"), dict):
            return data
    except (OSError, ValueError) as exc:
        logger.debug("clip index unreadable: %s", exc)
    return {"clips": {}}


def try_owned_beat_background(
    topic: str,
    script: str,
    channel_id: str | None,
    *,
    duration: float,
    words: list[dict] | None = None,
):
    """Concat owned index clips onto scene-plan beats, or None (keep the single loop)."""
    del channel_id
    scenes = plan_scenes(script, topic, duration, words=words)
    ranked = assign_owned_clips(scenes, load_clip_index(), topic=topic)
    paths = [p for p in ranked if os.path.isfile(p)]
    if not paths:
        if ranked:
            logger.debug("owned beat cuts: index paths are not on disk; keeping single loop")
        return None
    from assets.types import AssetResult

    logger.info("owned beat cuts: %s clip(s) from clip_index (not stock)", len(paths))
    if len(paths) >= 2 and len(scenes) >= 2:
        try:
            from assets.composite import compose_scene_matched_background

            segments = [
                (os.path.abspath(paths[i]), float(scenes[i].end - scenes[i].start))
                for i in range(min(len(paths), len(scenes)))
            ]
            composed = compose_scene_matched_background(segments, duration)
            return AssetResult(path=composed.path, provider="owned", query=topic)
        except Exception as exc:
            logger.info("owned beat concat failed; looping first clip: %s", exc)
    return AssetResult(path=paths[0], provider="owned", query=topic)
