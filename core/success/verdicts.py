"""Your verdict per video, against the audience's (#935).

Every video gets a report card from the engine; until now none got one from you. A
verdict is a 1-5 rating and a line of why, given in `ops review-week` (#936). Set against
the views, it says where your gut and the audience agree - and the two lists worth a look:
videos you loved that the audience did not, and ones you rated low that did well.

Views are ranked into thirds among the measured videos (views > 0); a rating of 4-5 agrees
with the top third, 3 with the middle, 1-2 with the bottom. Decision 94 (S05): the engine's
grade is set against the same views the same way - your gut tracked them, the grade did not.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.success.verdicts")

VERDICTS_FILE = os.path.join(DATA_DIR, "verdicts.json")
MIN_RATED = 3
GRADE_AGREE = 0.5  # S05, decision 94: half the measured videos in their views' third ...
GRADE_MIN = 30  # ... of at least 30 graded - chance is one in three


def _read() -> dict[str, Any]:
    try:
        with open(VERDICTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load(channel_id: str) -> dict[str, dict[str, Any]]:
    """{video_id: {rating, note, title, at}} for the channel."""
    entry = _read().get(channel_id)
    return entry if isinstance(entry, dict) else {}


def record(channel_id: str, video_id: str, rating: int, *, note: str = "", title: str = "") -> None:
    rating = int(rating)
    if not 1 <= rating <= 5:
        raise ValueError(f"a verdict is 1-5, got {rating}")
    data = _read()
    channel = data.setdefault(channel_id, {})
    channel[video_id] = {
        "rating": rating,
        "note": note.strip(),
        "title": title.strip(),
        "at": date.today().isoformat(),
    }
    os.makedirs(os.path.dirname(VERDICTS_FILE) or ".", exist_ok=True)
    tmp = f"{VERDICTS_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, VERDICTS_FILE)


def _third(rank: int, total: int) -> str:
    """ "top" / "middle" / "bottom" for a 0-based views rank (0 = most views)."""
    if rank < total / 3:
        return "top"
    if rank >= total - total / 3:
        return "bottom"
    return "middle"


def _agrees(rating: int, third: str) -> bool:
    return {"top": rating >= 4, "middle": rating == 3, "bottom": rating <= 2}[third]


def _scored(channel_id: str) -> dict[str, Any]:
    """Your ratings set against the views ranking (#940: the comparable measure)."""
    from core.success.videos import channel_videos, comparable_views

    verdicts = load(channel_id)
    # #1596: on a measure most rated videos have - 7-day views reached 3 of 28 ratings, and a
    # floor of 3 still let them win (live, 10-28)
    cover_min = min(len(verdicts), max(MIN_RATED, len(verdicts) // 2))
    ranked, heading, unit = comparable_views(
        channel_videos(channel_id), cover=set(verdicts), cover_min=cover_min
    )
    rated = [(i, v, value) for i, (v, value) in enumerate(ranked) if v.video_id in verdicts]
    agreed = 0
    loved, doubted = [], []
    for rank, video, value in rated:
        rating = int(verdicts[video.video_id]["rating"])
        third = _third(rank, len(ranked))
        agreed += _agrees(rating, third)
        if rating >= 4 and third == "bottom":
            loved.append(f'"{video.title}" (you: {rating}, {value:,} {unit})')
        if rating <= 2 and third == "top":
            doubted.append(f'"{video.title}" (you: {rating}, {value:,} {unit})')
    return {"measured": len(ranked), "rated": len(rated), "agreed": agreed, "loved": loved,
            "doubted": doubted, "heading": heading}  # fmt: skip


def agreement(channel_id: str) -> tuple[int, int]:
    """(agreed, rated) for the review history (#943)."""
    scored = _scored(channel_id)
    return scored["agreed"], scored["rated"]


def grade_agreement(channel_id: str) -> tuple[int, int]:
    """(agreed, graded): measured videos whose grade sits in the same third as their views.

    Decision 94 (S05): both ranked in thirds over the videos that have a grade - chance is one
    in three. On 11-01 the grade agreed on 15 of 40 (7-day views) while your verdicts tracked them.
    """
    from core import video_grade
    from core.success import videos

    ranked, _heading, _unit = videos.comparable_views(videos.channel_videos(channel_id))
    graded: list[tuple[str, float]] = []
    for video, _value in ranked:
        if not video.run_id:
            continue
        try:
            grade = video_grade.grade_run(int(video.run_id))
        except Exception as exc:
            logger.debug("verdicts: grade for run %s unavailable: %s", video.run_id, exc)
            continue
        if grade is not None:
            graded.append((video.video_id, float(grade.score)))
    total = len(graded)
    by_grade = {vid: i for i, (vid, _s) in enumerate(sorted(graded, key=lambda p: -p[1]))}
    agreed = sum(1 for i, (vid, _s) in enumerate(graded)
                 if _third(i, total) == _third(by_grade[vid], total))  # fmt: skip
    return agreed, total


def _grade_line(channel_id: str) -> str:
    agreed, graded = grade_agreement(channel_id)
    if not graded:
        return "  the grade against the audience: no graded video has views yet"
    return (f"  the grade against the audience: {agreed} of {graded} in the same third "
            f"({agreed / graded:.0%}; chance is 1 in 3) - it gates nothing (decision 94)")  # fmt: skip


def verdict_report(channel_id: str) -> list[str]:
    scored = _scored(channel_id)
    head = f"Your verdicts vs the audience - {channel_id}"
    rated, agreed = scored["rated"], scored["agreed"]
    if rated < MIN_RATED:
        return [
            head,
            f"  {rated} rated video(s) with views; rate {MIN_RATED - rated} more "
            "(py -m scripts.ops review-week) and this compares your gut with the views.",
            _grade_line(channel_id),
        ]
    lines = [
        f"{head} ({rated} rated videos with views)",
        f"  agreed on {agreed} of {rated} ({agreed / rated:.0%}) - {scored['heading']} ranked "
        f"in thirds over {scored['measured']} measured videos",
    ]
    if scored["loved"]:
        lines.append("  rated 4-5, landed in the bottom third: " + "; ".join(scored["loved"]))
    if scored["doubted"]:
        lines.append("  rated 1-2, landed in the top third: " + "; ".join(scored["doubted"]))
    lines.append(_grade_line(channel_id))
    return lines
