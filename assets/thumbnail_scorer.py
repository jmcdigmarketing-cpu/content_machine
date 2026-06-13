"""
Score thumbnail clickability before publish (vision LLM + heuristic fallback).
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from config.channels import resolve_channel_id
from core.llm_client import get_model, get_openai_client
from core.logging import get_logger
from storage.repositories.thumbnail_scores import get_thumbnail_score_repository

logger = get_logger("assets.thumbnail_scorer")


@dataclass
class ThumbnailScore:
    curiosity: float
    clarity: float
    contrast: float
    emotion: float
    overall: float
    suggestions: List[str] = field(default_factory=list)
    source: str = "heuristic"
    image_path: str = ""
    topic: str = ""
    channel_id: str = "default"

    def to_dict(self):
        return asdict(self)


def _scorer_enabled() -> bool:
    return os.getenv("THUMBNAIL_SCORER_ENABLED", "").lower() in ("1", "true", "yes")


def _clamp(score: float) -> float:
    return round(max(0.0, min(100.0, float(score))), 2)


def _heuristic_score(image_path: str, topic: str) -> ThumbnailScore:
    """Deterministic fallback when vision API is unavailable."""
    topic_l = (topic or "").lower()
    curiosity = 45.0
    clarity = 50.0
    contrast = 40.0
    emotion = 42.0
    suggestions: List[str] = []

    hooks = ("why", "how", "truth", "debate", "exposed", "shocking", "vs")
    if any(h in topic_l for h in hooks):
        curiosity += 15
    if len(topic) < 55:
        clarity += 8

    try:
        from PIL import Image, ImageStat

        with Image.open(image_path) as img:
            gray = img.convert("L")
            stat = ImageStat.Stat(gray)
            spread = (stat.stddev[0] if stat.stddev else 0) or 0
            contrast = _clamp(35 + spread * 1.8)
            w, h = img.size
            if w and h and 0.45 <= (w / h) <= 0.65:
                clarity += 10
    except Exception as e:
        logger.debug("PIL heuristic skipped: %s", e)
        suggestions.append("Could not analyze image contrast locally.")

    if contrast < 50:
        suggestions.append("Increase contrast between subject and background.")
    if curiosity < 55:
        suggestions.append("Add a clearer curiosity hook in the title overlay.")
    if emotion < 50:
        suggestions.append("Use a stronger facial expression or action freeze-frame.")

    scores = [_clamp(curiosity), _clamp(clarity), contrast, _clamp(emotion)]
    overall = _clamp(sum(scores) / len(scores))

    return ThumbnailScore(
        curiosity=scores[0],
        clarity=scores[1],
        contrast=scores[2],
        emotion=scores[3],
        overall=overall,
        suggestions=suggestions[:4],
        source="heuristic",
        image_path=image_path,
        topic=topic,
    )


def _vision_score(image_path: str, topic: str, channel_id: str) -> Optional[ThumbnailScore]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None

    model = os.getenv("OPENAI_VISION_MODEL") or get_model()
    ext = os.path.splitext(image_path)[1].lower()
    mime = "image/jpeg"
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"

    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode("ascii")

    prompt = f"""Score this YouTube Shorts thumbnail for click-through potential.
Topic: {topic}
Channel: {channel_id}

Return ONLY valid JSON:
{{
  "curiosity": 0-100,
  "clarity": 0-100,
  "contrast": 0-100,
  "emotion": 0-100,
  "overall": 0-100,
  "suggestions": ["short tip 1", "short tip 2"]
}}
"""

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}",
                            },
                        },
                    ],
                }
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group())
        suggestions = [str(s) for s in (data.get("suggestions") or [])[:4] if s]
        return ThumbnailScore(
            curiosity=_clamp(data.get("curiosity", 0)),
            clarity=_clamp(data.get("clarity", 0)),
            contrast=_clamp(data.get("contrast", 0)),
            emotion=_clamp(data.get("emotion", 0)),
            overall=_clamp(data.get("overall", 0)),
            suggestions=suggestions,
            source="llm",
            image_path=image_path,
            topic=topic,
            channel_id=channel_id,
        )
    except Exception as e:
        logger.warning("Vision thumbnail score failed: %s", e)
        return None


def score_thumbnail(
    image_path: str,
    topic: str,
    channel_id: Optional[str] = None,
    *,
    persist: bool = True,
    content_run_id: Optional[int] = None,
) -> Optional[ThumbnailScore]:
    """
    Score a thumbnail image. Returns None when scorer disabled or file missing.
    Persists to thumbnail_scores when content_run_id is set.
    """
    if not _scorer_enabled():
        return None

    channel_id = resolve_channel_id(channel_id)
    path = (image_path or "").strip()
    if not path or not os.path.isfile(path):
        logger.debug("Thumbnail scorer: file not found %s", path)
        return None

    result = _vision_score(path, topic, channel_id) or _heuristic_score(path, topic)
    result.channel_id = channel_id
    result.image_path = path
    result.topic = topic

    if persist and content_run_id:
        try:
            get_thumbnail_score_repository().create(
                {
                    "content_run_id": content_run_id,
                    "channel_id": channel_id,
                    "image_path": path,
                    "topic": topic[:512],
                    "curiosity": result.curiosity,
                    "clarity": result.clarity,
                    "contrast": result.contrast,
                    "emotion": result.emotion,
                    "overall": result.overall,
                    "suggestions_json": json.dumps(result.suggestions),
                    "source": result.source,
                }
            )
        except Exception as e:
            logger.warning("Could not persist thumbnail score: %s", e)

    return result


def maybe_score_after_render(
    *,
    thumbnail_path: str,
    topic: str,
    channel_id: str,
    content_run_id: Optional[int],
) -> Optional[ThumbnailScore]:
    """Soft-fail wrapper for pipeline hook."""
    if not thumbnail_path or not content_run_id:
        return None
    try:
        return score_thumbnail(
            thumbnail_path,
            topic,
            channel_id,
            content_run_id=content_run_id,
        )
    except Exception as e:
        logger.warning("Thumbnail scoring skipped: %s", e)
        return None
