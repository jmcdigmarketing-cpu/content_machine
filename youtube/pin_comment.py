"""#105 Opt-in channel comment answering the top youtube_comments question.

The YouTube Data API has no comments.pin method. We post a channel-authored
top-level comment (commentThreads.insert) so it appears in the thread; that is
the honest substitute, not a Studio pin. Profanity filter stays in front.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from apis.youtube_comments_signal import _is_clean
from apis.youtube_quota import record_call
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


def _comment_text(topic: str, question: str) -> str:
    return (
        f"Answering a common question on {topic}: {question} "
        "We don't invent dates — the Short sticks to sourced facts."
    )


def _pin_path() -> str:
    raw = (os.getenv("PIN_COMMENT_FILE") or "").strip()
    if raw:
        return raw
    from config.paths import DATA_DIR

    return os.path.join(DATA_DIR, "pin_comments.json")


def _load_pins() -> list[dict]:
    try:
        with open(_pin_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _save_pins(rows: list[dict]) -> None:
    path = _pin_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle)


def _parse_due(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def due_channels(now: datetime | None = None) -> list[str]:
    """Channel ids with a comment whose peak has passed. Empty when the file is missing."""
    moment = now or datetime.now(timezone.utc)
    found: list[str] = []
    for row in _load_pins():
        due = _parse_due(row.get("due"))
        if due is None or due > moment:
            continue
        channel = str(row.get("channel_id") or "tapin")
        if channel not in found:
            found.append(channel)
    return found


def due_count(now: datetime | None = None) -> int:
    """How many scheduled comments are due. A missing file is zero and writes nothing."""
    moment = now or datetime.now(timezone.utc)
    return sum(
        1
        for row in _load_pins()
        if (due := _parse_due(row.get("due"))) is not None and due <= moment
    )


def _insert(service, *, video_id: str, text: str) -> None:
    record_call("commentThreads.insert")  # wave 113: it booked nothing
    service.commentThreads().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {"snippet": {"textOriginal": text}},
            }
        },
    ).execute()


def post_due(service, now: datetime | None = None, *, channel_id: str = "") -> int:
    """Insert each comment whose peak has passed. Returns how many were posted."""
    moment = now or datetime.now(timezone.utc)
    rows = _load_pins()
    kept: list[dict] = []
    posted = 0
    for row in rows:
        due = _parse_due(row.get("due"))
        wanted = (channel_id or "") == "" or str(row.get("channel_id") or "") == channel_id
        if not wanted or due is None or due > moment:
            kept.append(row)
            continue
        try:
            _insert(
                service, video_id=str(row.get("video_id") or ""), text=str(row.get("text") or "")
            )
            posted += 1
        except Exception as exc:
            logger.debug("due pin insert skipped: %s", exc)
            kept.append(row)
    if posted or len(kept) != len(rows):
        _save_pins(kept)
    return posted


def maybe_pin_top_answer(
    service,
    *,
    video_id: str,
    topic: str,
    questions: list[str] | None = None,
    channel_id: str = "",
    now: datetime | None = None,
) -> PinCommentResult:
    if not _enabled():
        return PinCommentResult("skipped", "YOUTUBE_PIN_COMMENT off")
    if not video_id:
        return PinCommentResult("skipped", "No video_id")
    question = _first_clean(questions)
    if not question:
        return PinCommentResult("skipped", "no clean question")
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    from analytics.post_timing import next_peak

    peak = next_peak(channel_id or "tapin", moment)
    text = _comment_text(topic, question)
    if peak <= moment:
        try:
            _insert(service, video_id=video_id, text=text)
            return PinCommentResult("posted", question[:120])
        except Exception as exc:
            logger.debug("pin-comment insert skipped: %s", exc)
            return PinCommentResult("error", str(exc)[:200])
    rows = _load_pins()
    rows.append(
        {
            "video_id": video_id,
            "channel_id": channel_id,
            "text": text,
            "due": peak.isoformat(),
        }
    )
    _save_pins(rows)
    return PinCommentResult("scheduled", peak.isoformat())
