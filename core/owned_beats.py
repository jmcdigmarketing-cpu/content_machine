"""#416: cut owned gameplay between scene-plan beats. Never stock (§26)."""

from __future__ import annotations

import json
import os
from typing import Any

from apis.topic_tokens import content_tokens
from core.logging import get_logger
from video.scene_plan import Scene, plan_scenes

logger = get_logger("core.owned_beats")


def _topic_tokens(topic: str) -> list[str]:
    return content_tokens(topic)


def _labels(path: str, meta: dict[str, Any] | None) -> list[str]:
    """What names a clip's game: its folder, and its source when that is a label ("UFC 5")
    rather than a file path or a link."""
    labels = [os.path.basename(os.path.dirname(str(path)))]
    source = str((meta or {}).get("source") or "")
    if source and not any(mark in source for mark in ("/", "\\", ":")):
        labels.append(source)
    return labels


def topic_clips(index: dict[str, Any], *, topic: str, channel_id: str | None = None) -> list[str]:
    """Clip-index paths the topic names, longest first.

    A clip counts when the topic says every word of its game's name, or when its folder is
    the one the footage chooser picks for the topic (a playlist key, the topic's sport).
    #955: zero-hit clips used to be taken too. Then a topic word anywhere in the path was
    enough: "World Cup" matched the "open world" directory (27 GTA V clips) and "box office"
    matched "Xbox" in a capture's file name.
    """
    from assets.local_provider import _folder_words, choose_footage

    clips = (index or {}).get("clips") or {}
    if not isinstance(clips, dict):
        return []
    said = set(_topic_tokens(topic))
    folders = sorted({os.path.dirname(str(path)) for path in clips if path})
    try:
        chosen, _how = choose_footage(topic, folders, channel_id, use_llm=False)
    except Exception as exc:
        logger.debug("owned beats: footage choice skipped: %s", exc)
        chosen = None
    ranked: list[tuple[float, str]] = []
    for path, meta in clips.items():
        if not path:
            continue
        named = os.path.dirname(str(path)) == chosen
        for label in _labels(str(path), meta):
            words = _folder_words(label)
            named = named or bool(words and all(word in said for word in words))
        if not named:
            continue
        ranked.append((float((meta or {}).get("duration_s") or 0.0), str(path)))
    ranked.sort(key=lambda row: row[0], reverse=True)
    return [path for _dur, path in ranked]


def assign_owned_clips(
    scenes: list[Scene],
    index: dict[str, Any],
    *,
    topic: str,
    channel_id: str | None = None,
) -> list[str]:
    """Map beats to clip_index paths. Empty index -> [] (keep the single loop).

    Only clips that name something in the topic (`topic_clips`, #955).
    """
    clips = (index or {}).get("clips") or {}
    if not scenes or not isinstance(clips, dict) or not clips:
        return []
    paths = []
    for path in topic_clips(index, topic=topic, channel_id=channel_id):
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
        if hud is None and not os.path.isfile(path):
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
    scenes = plan_scenes(script, topic, duration, words=words)
    ranked = assign_owned_clips(scenes, load_clip_index(), topic=topic, channel_id=channel_id)
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
            return AssetResult(
                path=composed.path, provider="owned", source_id="footage:owned:", query=topic
            )
        except Exception as exc:
            logger.info("owned beat concat failed; looping first clip: %s", exc)
    return AssetResult(path=paths[0], provider="owned", source_id="footage:owned:", query=topic)
