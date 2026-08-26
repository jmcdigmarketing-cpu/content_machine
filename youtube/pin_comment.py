"""#105 Opt-in channel comment answering the top youtube_comments question.

The YouTube Data API has no comments.pin method. We post a channel-authored
top-level comment (commentThreads.insert) so it appears in the thread; that is
the honest substitute, not a Studio pin. Profanity filter stays in front.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from apis.youtube_comments_signal import _is_clean
from core.logging import get_logger

logger = get_logger("youtube.pin_comment")


@dataclass
class PinCommentResult:
    status: str
    detail: str | None = None


def _enabled() -> bool:
    return os.getenv("YOUTUBE_PIN_COMMENT", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _first_clean(questions: list[str] | None) -> str | None:
    for raw in questions or []:
        text = str(raw or "").strip()
        if text and _is_clean(text):
            return text
    return None


def maybe_pin_top_answer(
    service,
    *,
    video_id: str,
    topic: str,
    questions: list[str] | None = None,
) -> PinCommentResult:
    if not _enabled():
        return PinCommentResult("skipped", "YOUTUBE_PIN_COMMENT off")
    if not video_id:
        return PinCommentResult("skipped", "No video_id")
    question = _first_clean(questions)
    if not question:
        return PinCommentResult("skipped", "no clean question")
    body_text = (
        f"Answering a common question on {topic}: {question} "
        "We don't invent dates — the Short sticks to sourced facts."
    )
    try:
        service.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {"textOriginal": body_text},
                    },
                }
            },
        ).execute()
        return PinCommentResult("posted", question[:120])
    except Exception as exc:
        logger.debug("pin-comment insert skipped: %s", exc)
        return PinCommentResult("error", str(exc)[:200])
